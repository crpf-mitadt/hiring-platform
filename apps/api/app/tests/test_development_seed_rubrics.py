import json
from datetime import timedelta

from app import seed
from app.core.config import get_settings
from app.db.base import utcnow
from app.models import (
    Application,
    ApplicationAccessSession,
    ApplicationAccessToken,
    ApplicationIntroVideo,
    ApplicationStage,
    ApplicationStageHistory,
    AssessmentAssignment,
    AssessmentAssignmentStatus,
    AssessmentAttempt,
    AssessmentAttemptStatus,
    AssessmentResponse,
    AssessmentResult,
    AuditEvent,
    Candidate,
    HiringDecision,
    HiringDecisionType,
    InterviewSchedule,
    Job,
    JobRubricVersion,
    RubricVersionStatus,
    ScreeningCriterionResult,
    ScreeningEvidence,
    ScreeningJob,
    ScreeningJobStatus,
    ScreeningRun,
    ScreeningRunStatus,
)
from app.services.jobs import approve_rubric_version
from app.services.rubric_utils import rubric_payload_hash
from sqlalchemy import select


class _SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, traceback):
        if exc_type:
            self.session.rollback()
        return False


def _run_seed(monkeypatch, db_session):
    settings = get_settings()
    previous_environment = settings.environment
    settings.environment = "development"
    monkeypatch.setattr(seed, "SessionLocal", lambda: _SessionContext(db_session))
    try:
        seed.seed_development_data(staff_password="development-password")
    finally:
        settings.environment = previous_environment


def _run_reset(monkeypatch, db_session):
    settings = get_settings()
    previous_environment = settings.environment
    settings.environment = "development"
    monkeypatch.setattr(seed, "SessionLocal", lambda: _SessionContext(db_session))
    try:
        seed.reset_demo_applications()
    finally:
        settings.environment = previous_environment


def _current_version(db_session, title: str) -> JobRubricVersion:
    job = db_session.scalar(select(Job).where(Job.title == title))
    assert job is not None
    rubric = job.rubrics[0]
    version = db_session.get(JobRubricVersion, rubric.current_version_id)
    assert version is not None
    return version


def _payload_text(payload: dict) -> str:
    excluded_keys = {
        "contains_student_facing",
        "contains_teaching",
        "demo_marker",
        "extraction_warnings",
        "role_category",
    }
    values: list[str] = []

    def collect(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                if key not in excluded_keys:
                    collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)
        elif isinstance(value, str):
            values.append(value)

    collect(payload)
    return json.dumps(values, sort_keys=True).lower()


def test_demo_rubric_provider_marker_fits_model_constraint():
    proposed_by_column = JobRubricVersion.__table__.columns["proposed_by"]

    assert proposed_by_column.type.length == 30
    assert len(seed.DEMO_RUBRIC_PROVIDER) <= proposed_by_column.type.length


def test_full_stack_seed_payload_matches_current_vacancy_without_faculty_contamination(
    monkeypatch,
    db_session,
    settings_tmp,
):
    _run_seed(monkeypatch, db_session)

    version = _current_version(db_session, "Full Stack Developer")
    payload = version.structured_jd_payload
    text = _payload_text(payload)

    assert payload["domain"] == "Full-stack web and application development"
    assert payload["minimum_experience_months"] == 24
    assert payload["maximum_experience_months"] == 36
    for required in [
        "PHP",
        "Laravel",
        "WordPress",
        "JavaScript",
        "HTML",
        "CSS",
        "SQL",
        "MySQL",
        "MongoDB",
        "React.js",
        "Node.js",
        "Express",
        "GitLab",
        "GitHub",
        "Bash scripting",
        "Full-stack development",
    ]:
        assert required.lower() in text
    for forbidden in ["teaching", "student-facing", "student facing", "research"]:
        assert forbidden not in text


def test_content_writer_seed_payload_is_content_specific(monkeypatch, db_session, settings_tmp):
    _run_seed(monkeypatch, db_session)

    payload = _current_version(db_session, "Content Writer").structured_jd_payload
    text = _payload_text(payload)

    for required in [
        "content writing",
        "editing",
        "proofreading",
        "copywriting",
        "written english communication",
        "seo",
        "keyword research",
        "web content",
        "wordpress",
        "simplify",
    ]:
        assert required in text
    for forbidden in ["full-stack", "laravel", "node.js", "teaching", "faculty"]:
        assert forbidden not in text


def test_faculty_seed_payloads_keep_academic_teaching_and_research_requirements(
    monkeypatch,
    db_session,
    settings_tmp,
):
    _run_seed(monkeypatch, db_session)

    for title in [
        "Engineering & Technology Faculty",
        "Creative Cluster Faculty",
        "Management & Humanities Faculty",
    ]:
        version = _current_version(db_session, title)
        payload = version.structured_jd_payload
        text = _payload_text(payload)
        assert payload["contains_teaching"] is True
        assert payload["contains_student_facing"] is True
        assert "teaching" in text
        assert "research" in text
        assert "academic" in text


def test_all_seeded_current_versions_are_approved_hashed_and_coherent(
    monkeypatch,
    db_session,
    settings_tmp,
):
    _run_seed(monkeypatch, db_session)

    for vacancy in seed.VACANCIES:
        job = db_session.scalar(
            select(Job).where(Job.title == vacancy["title"], Job.source_reference == vacancy["source_reference"])
        )
        assert job is not None
        assert job.department.name == vacancy["department"]
        assert job.role_category == vacancy["role_category"]
        rubric = job.rubrics[0]
        version = db_session.get(JobRubricVersion, rubric.current_version_id)
        assert version is not None
        assert version.status == RubricVersionStatus.APPROVED
        assert version.proposed_by == seed.DEMO_RUBRIC_PROVIDER
        assert version.structured_jd_payload["job_id"] == job.id
        assert version.structured_jd_payload["job_title"] == vacancy["title"]
        assert version.structured_jd_payload["department"] == vacancy["department"]
        assert version.criteria == version.structured_jd_payload["scoring_rubric"]
        assert version.approved_payload_sha256 == rubric_payload_hash(version)
        assert {criterion["criterion_id"] for criterion in version.criteria} == {
            criterion["criterion_id"] for criterion in vacancy["criteria"]
        }
        assert sum(criterion["weight"] for criterion in version.criteria) == 100


def test_non_teaching_seed_payloads_do_not_get_faculty_only_requirements(
    monkeypatch,
    db_session,
    settings_tmp,
):
    _run_seed(monkeypatch, db_session)

    for title in ["Content Writer", "Full Stack Developer"]:
        payload = _current_version(db_session, title).structured_jd_payload
        text = _payload_text(payload)
        assert payload["contains_teaching"] is False
        assert payload["contains_student_facing"] is False
        for forbidden in ["teaching", "student-facing", "student facing", "academic journal", "research papers"]:
            assert forbidden not in text


def test_seed_is_idempotent_and_does_not_duplicate_corrected_versions(
    monkeypatch,
    db_session,
    settings_tmp,
):
    _run_seed(monkeypatch, db_session)
    counts_before = {
        job.title: len(job.rubrics[0].versions)
        for job in db_session.scalars(select(Job).where(Job.source_reference.is_not(None)))
    }

    _run_seed(monkeypatch, db_session)
    counts_after = {
        job.title: len(job.rubrics[0].versions)
        for job in db_session.scalars(select(Job).where(Job.source_reference.is_not(None)))
    }

    assert counts_after == counts_before


def test_seed_repairs_old_bad_full_stack_approved_version_without_mutating_history(
    monkeypatch,
    db_session,
    settings_tmp,
):
    vacancy = next(entry for entry in seed.VACANCIES if entry["title"] == "Full Stack Developer")
    recruiter = seed._user(db_session, "hr.recruiter@mitadt.demo", "MIT-ADT HR Recruiter", seed.Role.HR_RECRUITER, "pw")
    reviewer = seed._user(
        db_session,
        "department.reviewer@mitadt.demo",
        "MIT-ADT Department Reviewer",
        seed.Role.DEPARTMENT_REVIEWER,
        "pw",
    )
    admin = seed._user(db_session, "admin@mitadt.demo", "MIT-ADT Hiring Administrator", seed.Role.HIRING_ADMIN, "pw")
    school = seed._school(db_session, "MIT Art, Design and Technology University")
    department = seed._department(db_session, school, vacancy["department"])
    assessment_version = seed._assessment_template_version(db_session, admin, vacancy)
    jd_document = seed._document(
        db_session,
        recruiter,
        seed.DocumentPurpose.JOB_JD,
        "full-stack-developer-demo-jd.txt",
        vacancy["description"].encode("utf-8"),
        "text/plain",
    )
    job = seed._job(db_session, vacancy, school, department, recruiter, reviewer, jd_document, assessment_version)
    bad_payload = {
        "schema_version": "structured-jd-v1",
        "job_id": job.id,
        "source_document_id": jd_document.id,
        "extraction_method": "mock_gemma",
        "job_title": "Full Stack Developer",
        "department": "DIDU",
        "role_summary": "Generic teaching mock payload.",
        "required_skills": ["Teaching", "Python"],
        "preferred_skills": ["Research"],
        "minimum_experience_months": 24,
        "domain": "DIDU",
        "scoring_rubric": [
            {"criterion_id": "core-teaching", "name": "Core teaching capability", "category": "teaching", "weight": 35}
        ],
        "demo_marker": seed.DEMO_MARKER,
    }
    rubric = job.rubrics[0]
    bad_version = JobRubricVersion(
        rubric=rubric,
        version_number=1,
        status=RubricVersionStatus.DRAFT,
        proposed_by="mock-rubric",
        source_jd_document_id=jd_document.id,
        source_jd_sha256=jd_document.sha256,
        source_structured_jd_schema_version="structured-jd-v1",
        structured_jd_payload=bad_payload,
        criteria=vacancy["criteria"],
        engine_mapping={"source": "mock-rubric"},
    )
    db_session.add(bad_version)
    db_session.flush()
    approve_rubric_version(db_session, recruiter, bad_version.id)
    db_session.commit()

    _run_seed(monkeypatch, db_session)

    repaired_job = db_session.get(Job, job.id)
    assert repaired_job is not None
    repaired_rubric = repaired_job.rubrics[0]
    repaired_current = db_session.get(JobRubricVersion, repaired_rubric.current_version_id)
    historical_bad = db_session.get(JobRubricVersion, bad_version.id)
    assert repaired_current is not None
    assert historical_bad is not None
    assert repaired_current.id != historical_bad.id
    assert repaired_current.version_number == 2
    assert historical_bad.structured_jd_payload == bad_payload
    assert historical_bad.criteria == vacancy["criteria"]
    assert "teaching" not in _payload_text(repaired_current.structured_jd_payload)
    assert repaired_current.approved_payload_sha256 == rubric_payload_hash(repaired_current)

    count_after_repair = len(repaired_rubric.versions)
    _run_seed(monkeypatch, db_session)
    assert len(repaired_rubric.versions) == count_after_repair


def test_reset_demo_applications_removes_dependent_demo_records(
    monkeypatch,
    db_session,
    settings_tmp,
):
    _run_seed(monkeypatch, db_session)
    job = db_session.scalar(select(Job).where(Job.title == "Full Stack Developer"))
    actor = db_session.scalar(select(seed.User).where(seed.User.email == "admin@mitadt.demo"))
    assert job is not None
    assert actor is not None
    candidate = Candidate(full_name="Synthetic Seed Candidate", email="seed.candidate@example.org")
    application = Application(
        candidate=candidate,
        job=job,
        submitted_at=utcnow(),
        resume_document_ref="synthetic-reset-resume",
        current_stage=ApplicationStage.SCREENING_REVIEW,
        application_payload={"demo": True},
        scoring_safe_payload={"skills": ["PHP"]},
    )
    db_session.add(application)
    db_session.flush()
    run = ScreeningRun(
        application=application,
        rubric_version_id=job.rubrics[0].current_version_id,
        provider="mock",
        provider_engine_version="test",
        run_status=ScreeningRunStatus.COMPLETE,
    )
    db_session.add(run)
    db_session.flush()
    criterion = ScreeningCriterionResult(
        screening_run=run,
        criterion_id="full_stack_experience",
        criterion_name="Full stack delivery experience",
        category="experience",
        weight=35,
        status="matched",
        match_fraction=1.0,
        weighted_score=35.0,
        explanation="Synthetic evidence.",
    )
    db_session.add(criterion)
    db_session.flush()
    db_session.add(
        ScreeningEvidence(
            criterion_result=criterion,
            source_type="resume",
            source_document_id="synthetic",
            exact_text="Built PHP and Laravel applications.",
            evidence_status="supported",
        )
    )
    db_session.add(ScreeningJob(screening_run=run, status=ScreeningJobStatus.COMPLETED))
    template_version = db_session.get(seed.AssessmentTemplateVersion, job.assessment_template_version_id)
    assert template_version is not None
    assignment = AssessmentAssignment(
        application=application,
        template_version_id=template_version.id,
        assigned_by_id=actor.id,
        assigned_at=utcnow(),
        status=AssessmentAssignmentStatus.SUBMITTED,
        version_snapshot={"demo": True},
    )
    db_session.add(assignment)
    db_session.flush()
    attempt = AssessmentAttempt(
        assignment=assignment,
        application=application,
        status=AssessmentAttemptStatus.SUBMITTED,
        started_at=utcnow(),
        submitted_at=utcnow(),
    )
    db_session.add(attempt)
    db_session.flush()
    question = template_version.questions[0]
    db_session.add(AssessmentResponse(attempt=attempt, question=question, selected_option_ids=[], saved_at=utcnow()))
    db_session.add(
        AssessmentResult(
            attempt=attempt,
            achieved_marks=1,
            total_marks=1,
            percentage=100,
            question_breakdown=[],
            completed_at=utcnow(),
        )
    )
    db_session.add(
        ApplicationAccessToken(
            application=application,
            token_hash="a" * 64,
            created_at=utcnow(),
            expires_at=utcnow() + timedelta(days=1),
        )
    )
    db_session.add(
        ApplicationAccessSession(
            application=application,
            session_token_hash="b" * 64,
            created_at=utcnow(),
            expires_at=utcnow() + timedelta(days=1),
        )
    )
    db_session.add(ApplicationIntroVideo(application=application))
    db_session.add(InterviewSchedule(application=application))
    db_session.add(
        ApplicationStageHistory(
            application=application,
            previous_stage=ApplicationStage.SCREENING_COMPLETE,
            new_stage=ApplicationStage.SCREENING_REVIEW,
            actor=actor,
            timestamp=utcnow(),
        )
    )
    db_session.add(
        HiringDecision(
            application=application,
            decision=HiringDecisionType.HOLD,
            actor=actor,
            timestamp=utcnow(),
            remarks="Synthetic hold.",
        )
    )
    db_session.add(
        AuditEvent(
            actor=actor,
            action="application.synthetic",
            entity_type="application",
            entity_id=application.id,
            timestamp=utcnow(),
        )
    )
    db_session.add(
        AuditEvent(
            actor=actor,
            action="screening.synthetic",
            entity_type="screening_run",
            entity_id=run.id,
            timestamp=utcnow(),
        )
    )
    db_session.commit()

    _run_reset(monkeypatch, db_session)

    assert db_session.get(Application, application.id) is None
    assert db_session.scalar(select(ScreeningRun).where(ScreeningRun.id == run.id)) is None
    assert (
        db_session.scalar(select(ScreeningCriterionResult).where(ScreeningCriterionResult.id == criterion.id))
        is None
    )
    assert db_session.scalar(select(ScreeningEvidence)) is None
    assert db_session.scalar(select(ScreeningJob).where(ScreeningJob.screening_run_id == run.id)) is None
    assert db_session.scalar(select(AssessmentAssignment).where(AssessmentAssignment.id == assignment.id)) is None
    assert db_session.scalar(select(AssessmentAttempt).where(AssessmentAttempt.id == attempt.id)) is None
    assert (
        db_session.scalar(select(ApplicationAccessToken).where(ApplicationAccessToken.application_id == application.id))
        is None
    )
    assert (
        db_session.scalar(
            select(ApplicationAccessSession).where(ApplicationAccessSession.application_id == application.id)
        )
        is None
    )
    assert (
        db_session.scalar(select(ApplicationIntroVideo).where(ApplicationIntroVideo.application_id == application.id))
        is None
    )
    assert (
        db_session.scalar(select(InterviewSchedule).where(InterviewSchedule.application_id == application.id))
        is None
    )
    assert (
        db_session.scalar(
            select(ApplicationStageHistory).where(ApplicationStageHistory.application_id == application.id)
        )
        is None
    )
    assert db_session.scalar(select(HiringDecision).where(HiringDecision.application_id == application.id)) is None
    assert db_session.scalar(select(AuditEvent).where(AuditEvent.entity_id.in_([application.id, run.id]))) is None
