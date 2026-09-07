from urllib.parse import parse_qs, urlparse

from app.core.config import get_settings
from app.models import (
    Application,
    ApplicationAccessToken,
    AssessmentAssignment,
    AssessmentOption,
    AssessmentQuestion,
    AssessmentQuestionType,
    AssessmentTemplate,
    AssessmentTemplateStatus,
    AssessmentTemplateVersion,
    IntroVideoMode,
    Job,
    ScreeningJob,
    ScreeningRun,
)
from app.services.scoring_projection import BLOCKED_SCORING_KEYS
from sqlalchemy import select


def _public_resume(client):
    response = client.post(
        "/api/documents/public/resumes",
        files={"file": ("resume.pdf", b"%PDF-1.4 synthetic resume", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _public_photo(client):
    response = client.post(
        "/api/documents/public/photos",
        files={"file": ("photo.png", b"\x89PNG\r\n synthetic photo", "image/png")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _application_payload(resume_id: str, photo_id: str) -> dict:
    return {
        "basic": {
            "position": "Full Stack Developer",
            "designation": "Full Stack Developer",
            "full_name": "Aditi Kulkarni",
            "email": "aditi@example.org",
            "phone": "9999999999",
            "date_of_birth": "1994-03-12",
            "gender": "Female",
            "mother_tongue": "Marathi",
            "previously_employed_with_mit_adt": "No",
            "specialisation": "Web applications",
        },
        "education": {
            "ug": {
                "degree": "B.Tech",
                "specialisation": "Computer Science",
                "passing_year": "2016",
                "marks_or_cgpa": "8.2",
                "university": "Synthetic University",
            },
            "completed_pg": "No",
            "pg": {},
        },
        "experience": {
            "teaching_years": 0,
            "research_years": 0,
            "industry_years": 3,
            "total_years": 3,
        },
        "research": {},
        "qualifications": {"net": False, "set": False},
        "languages": {"english": True, "hindi": True, "marathi": True},
        "documents": {"salary": {"current_salary_lpa": "6.5", "expected_salary_lpa": "8.0"}},
        "resume_document_id": resume_id,
        "photo_document_id": photo_id,
        "applied_designation": "Full Stack Developer",
    }


def _submit_public_application(client, published_job):
    resume = _public_resume(client)
    photo = _public_photo(client)
    response = client.post(
        f"/api/applications/public/jobs/{published_job['id']}/apply",
        json=_application_payload(resume["id"], photo["id"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _extract_token(continuation_url: str) -> str:
    parsed = urlparse(continuation_url)
    return parse_qs(parsed.query)["token"][0]


def test_public_application_creates_scoped_access_and_auto_screening(client, db_session, published_job):
    settings = get_settings()
    previous_environment = settings.environment
    settings.environment = "development"
    try:
        submitted = _submit_public_application(client, published_job)
    finally:
        settings.environment = previous_environment

    assert submitted["continuation_url"]
    application = db_session.get(Application, submitted["id"])
    assert application is not None
    assert application.candidate.user_id is None
    assert application.resume_document_id
    assert application.photo_document_id
    assert db_session.scalar(select(ScreeningRun).where(ScreeningRun.application_id == application.id)) is not None
    assert db_session.scalar(select(ScreeningJob)) is not None

    token = _extract_token(submitted["continuation_url"])
    stored_token = db_session.scalar(select(ApplicationAccessToken))
    assert stored_token is not None
    assert stored_token.token_hash != token
    assert token not in stored_token.token_hash

    exchange = client.post("/api/applications/application-access/exchange", json={"token": token})
    assert exchange.status_code == 200, exchange.text
    assert client.post("/api/applications/application-access/exchange", json={"token": token}).status_code == 401

    status = client.get("/api/applications/application-access/application")
    assert status.status_code == 200, status.text
    assert status.json()["id"] == application.id
    assert status.json()["status_label"] == "Application submitted"
    assert status.json()["progress"] == []
    assert status.json()["interview"] is None
    assert "score" not in status.text
    assert "evidence" not in status.text
    assert "aditi@example.org" not in status.text
    assert "Interview" not in status.text
    assert "Decision" not in status.text

    assert client.get("/api/jobs").status_code == 401


def test_scoring_safe_projection_excludes_personal_application_fields(client, db_session, published_job):
    submitted = _submit_public_application(client, published_job)
    application = db_session.get(Application, submitted["id"])
    assert application is not None

    projection_text = str(application.scoring_safe_payload).lower()
    for blocked in BLOCKED_SCORING_KEYS:
        assert blocked not in projection_text
    assert "aditi" not in projection_text
    assert "9999999999" not in projection_text
    assert "salary" not in projection_text
    assert "photo" not in projection_text


def test_application_scoped_assessment_can_be_completed_without_candidate_account(
    client,
    db_session,
    users,
    published_job,
):
    version = _assessment_version(db_session, users["admin"]["id"])
    job = db_session.get(Job, published_job["id"])
    job.assessment_template_version_id = version.id
    db_session.commit()

    settings = get_settings()
    previous_environment = settings.environment
    settings.environment = "development"
    try:
        submitted = _submit_public_application(client, published_job)
    finally:
        settings.environment = previous_environment
    token = _extract_token(submitted["continuation_url"])
    assert client.post("/api/applications/application-access/exchange", json={"token": token}).status_code == 200

    assignment = client.get("/api/applications/application-access/assessment")
    assert assignment.status_code == 200, assignment.text
    assignment_id = assignment.json()["id"]

    attempt = client.post(f"/api/applications/application-access/assessments/{assignment_id}/start")
    assert attempt.status_code == 200, attempt.text
    question = attempt.json()["questions"][0]
    option_id = question["options"][0]["id"]

    submitted_attempt = client.post(
        f"/api/applications/application-access/assessments/attempts/{attempt.json()['id']}/submit",
        json={"responses": [{"question_id": question["id"], "selected_option_ids": [option_id]}]},
    )
    assert submitted_attempt.status_code == 200, submitted_attempt.text
    assert submitted_attempt.json()["status"] == "SUBMITTED"

    dossier = client.get(
        f"/api/applications/{submitted['id']}/screening-dossier",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert dossier.status_code == 200, dossier.text
    assert dossier.json()["assessment"]["result"]["percentage"] == 100.0

    candidate_status = client.get("/api/applications/application-access/application")
    assert "percentage" not in candidate_status.text
    assert "score" not in candidate_status.text


def test_public_candidates_share_job_version_assessment_and_can_skip_required_video(
    client,
    db_session,
    users,
    published_job,
):
    version = _assessment_version(db_session, users["admin"]["id"])
    job = db_session.get(Job, published_job["id"])
    job.assessment_template_version_id = version.id
    job.intro_video_mode = IntroVideoMode.REQUIRED
    db_session.commit()

    settings = get_settings()
    previous_environment = settings.environment
    settings.environment = "development"
    try:
        first = _submit_public_application(client, published_job)
        second_resume = _public_resume(client)
        second_photo = _public_photo(client)
        second_payload = _application_payload(second_resume["id"], second_photo["id"])
        second_payload["basic"]["email"] = "second@example.org"
        second_payload["basic"]["full_name"] = "Second Candidate"
        second = client.post(f"/api/applications/public/jobs/{published_job['id']}/apply", json=second_payload).json()
    finally:
        settings.environment = previous_environment

    first_token = _extract_token(first["continuation_url"])
    assert client.post("/api/applications/application-access/exchange", json={"token": first_token}).status_code == 200
    first_assignment = client.get("/api/applications/application-access/assessment").json()
    first_attempt = client.post(
        f"/api/applications/application-access/assessments/{first_assignment['id']}/start"
    ).json()
    question = first_attempt["questions"][0]
    client.post(
        f"/api/applications/application-access/assessments/attempts/{first_attempt['id']}/submit",
        json={"responses": [{"question_id": question["id"], "selected_option_ids": [question["options"][0]["id"]]}]},
    )
    skipped = client.post("/api/applications/application-access/intro-video/skip")
    assert skipped.status_code == 200, skipped.text
    assert skipped.json()["status"] == "SKIPPED"

    second_application = db_session.get(Application, second["id"])
    first_application = db_session.get(Application, first["id"])
    first_assignment_record = db_session.scalar(
        select(AssessmentAssignment).where(AssessmentAssignment.application_id == first_application.id)
    )
    second_assignment_record = db_session.scalar(
        select(AssessmentAssignment).where(AssessmentAssignment.application_id == second_application.id)
    )
    assert first_assignment_record is not None
    assert second_assignment_record is not None
    assert first_assignment_record.template_version_id == version.id
    assert second_assignment_record.template_version_id == version.id
    assert (
        first_assignment_record.version_snapshot["questions"]
        == second_assignment_record.version_snapshot["questions"]
    )


def _assessment_version(db_session, actor_id: str) -> AssessmentTemplateVersion:
    template = AssessmentTemplate(
        title="Demo assessment for public flow",
        description="Synthetic assessment fixture",
        created_by_id=actor_id,
    )
    version = AssessmentTemplateVersion(
        template=template,
        version_number=1,
        status=AssessmentTemplateStatus.PUBLISHED,
        title="Demo assessment for public flow",
        instructions="Answer the fixture question.",
        duration_minutes=10,
        total_marks=1,
        content={"test": True},
        published_by_id=actor_id,
    )
    question = AssessmentQuestion(
        position=1,
        prompt="Who makes final hiring decisions?",
        question_type=AssessmentQuestionType.SINGLE_CHOICE,
        marks=1,
    )
    question.options = [
        AssessmentOption(position=1, label="A", text="Human reviewers", is_correct=True),
        AssessmentOption(position=2, label="B", text="An automated system", is_correct=False),
    ]
    version.questions.append(question)
    db_session.add(template)
    db_session.flush()
    template.current_version_id = version.id
    db_session.commit()
    return version
