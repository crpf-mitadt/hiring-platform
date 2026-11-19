from app.core.errors import InvalidTransition, NotFound, PermissionDenied
from app.core.security import require_any_role, role_values
from app.db.base import utcnow
from app.models import (
    Application,
    ApplicationStage,
    Candidate,
    DocumentPurpose,
    Job,
    JobRoleCategory,
    JobStatus,
    Role,
    User,
)
from app.schemas.applications import ApplicationCreate, PublicApplicationCreate
from app.services.application_access import continuation_url, create_application_access_token
from app.services.assessments import (
    application_assessment,
    assessment_assignment_read,
    assign_configured_assessment,
)
from app.services.audit import record_audit
from app.services.documents import get_document
from app.services.followup import (
    ensure_followup_records,
    interview_for_application,
    interview_read,
    intro_video_for_application,
    intro_video_read,
)
from app.services.scoring_projection import build_scoring_safe_application_projection
from app.services.system_actor import get_system_actor
from app.services.workflow import transition_application
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session


def submit_application(db: Session, actor: User, job_id: str, data: ApplicationCreate) -> Application:
    from app.services.screening import enqueue_screening_run

    if Role.CANDIDATE not in role_values(actor):
        raise PermissionDenied("Only candidates can submit applications")
    job = db.get(Job, job_id)
    if job is None:
        raise NotFound("Job not found")
    if job.status != JobStatus.PUBLISHED:
        raise InvalidTransition("Applications are only accepted for published jobs")

    candidate = None
    if data.candidate.user_id is None:
        data.candidate.user_id = actor.id
    if data.candidate.user_id != actor.id:
        raise PermissionDenied("Candidate can only submit their own profile")
    if data.candidate.user_id:
        candidate = db.scalar(select(Candidate).where(Candidate.user_id == data.candidate.user_id))
    if candidate is None:
        candidate = Candidate(**data.candidate.model_dump())
        db.add(candidate)
        db.flush()
    elif candidate.user_id != actor.id:
        raise PermissionDenied("Candidate can only submit their own profile")
    resume_document_id = data.resume_document_id or data.candidate.resume_document_id
    if resume_document_id:
        resume_document = get_document(db, resume_document_id)
        if resume_document.purpose != DocumentPurpose.RESUME:
            raise InvalidTransition("Applications require a resume document")
        if resume_document.uploaded_by_id != actor.id:
            raise PermissionDenied("Candidate can only attach their own uploaded resume")
        candidate.resume_document_id = resume_document.id
    if data.candidate.resume_document_ref:
        candidate.resume_document_ref = data.candidate.resume_document_ref

    existing_application = db.scalar(
        select(Application).where(Application.candidate_id == candidate.id).where(Application.job_id == job.id)
    )
    if existing_application is not None:
        enqueue_screening_run(db, application_id=existing_application.id, actor=actor)
        return existing_application

    application = Application(
        candidate=candidate,
        job=job,
        submitted_at=utcnow(),
        resume_document_ref=data.resume_document_ref or candidate.resume_document_ref,
        resume_document_id=resume_document_id or candidate.resume_document_id,
    )
    db.add(application)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        action="application.submit",
        entity_type="application",
        entity_id=application.id,
    )
    transition_application(
        db,
        application=application,
        actor=actor,
        new_stage=ApplicationStage.SCREENING_PENDING,
        system_transition=True,
    )
    enqueue_screening_run(db, application_id=application.id, actor=actor)
    return application


def submit_public_application(
    db: Session,
    job_id: str,
    data: PublicApplicationCreate,
) -> tuple[Application, str | None]:
    from app.services.screening import enqueue_screening_run

    job = db.get(Job, job_id)
    if job is None:
        raise NotFound("Job not found")
    if job.status != JobStatus.PUBLISHED:
        raise InvalidTransition("Applications are only accepted for published jobs")
    _validate_application_payload(job, data)

    resume_document = get_document(db, data.resume_document_id)
    if resume_document.purpose != DocumentPurpose.RESUME:
        raise InvalidTransition("Application resume document is required")
    photo_document = get_document(db, data.photo_document_id)
    if photo_document.purpose != DocumentPurpose.PHOTO:
        raise InvalidTransition("Application photo document is required")

    payload = data.model_dump(exclude={"resume_document_id", "photo_document_id", "applied_designation"})
    basic = payload["basic"]
    education = payload["education"]
    experience = payload["experience"]
    candidate = Candidate(
        full_name=basic["full_name"],
        email=basic["email"],
        phone=basic.get("phone"),
        education_profile=education,
        work_experience_profile=experience,
        resume_document_id=resume_document.id,
    )
    scoring_safe_payload = build_scoring_safe_application_projection(payload, job.role_category)
    application = Application(
        candidate=candidate,
        job=job,
        submitted_at=utcnow(),
        resume_document_id=resume_document.id,
        applied_designation=data.applied_designation or basic.get("designation") or job.designation,
        photo_document_id=photo_document.id,
        application_payload=payload,
        scoring_safe_payload=scoring_safe_payload,
    )
    db.add(application)
    db.flush()
    actor = get_system_actor(db)
    record_audit(
        db,
        actor_id=actor.id,
        action="application.public_submit",
        entity_type="application",
        entity_id=application.id,
    )
    transition_application(
        db,
        application=application,
        actor=actor,
        new_stage=ApplicationStage.SCREENING_PENDING,
        system_transition=True,
    )
    enqueue_screening_run(db, application_id=application.id, actor=actor)
    assign_configured_assessment(db, application, actor)
    ensure_followup_records(db, application)
    _, raw_token = create_application_access_token(db, application)
    return application, continuation_url(raw_token)


def list_applications(
    db: Session,
    actor: User,
    *,
    job_id: str | None = None,
    stage: ApplicationStage | None = None,
) -> list[Application]:
    if Role.CANDIDATE in role_values(actor) and len(role_values(actor)) == 1:
        stmt = (
            select(Application)
            .join(Candidate)
            .where(Candidate.user_id == actor.id)
            .order_by(Application.submitted_at.desc())
        )
    else:
        require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
        stmt = select(Application).order_by(Application.submitted_at.desc())
    if job_id:
        stmt = stmt.where(Application.job_id == job_id)
    if stage:
        stmt = stmt.where(Application.current_stage == stage)
    return list(db.scalars(stmt))


def get_application_for_actor(db: Session, actor: User, application_id: str) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise NotFound("Application not found")
    if Role.CANDIDATE in role_values(actor) and len(role_values(actor)) == 1:
        if application.candidate.user_id != actor.id:
            raise PermissionDenied("Candidate can only access their own application")
    else:
        require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    return application


def candidate_safe_status(application: Application) -> dict:
    assessment = application_assessment_for_read(application)
    intro_video = getattr(application, "_intro_video_read", None)
    return {
        "id": application.id,
        "job_id": application.job_id,
        "job_title": application.job.title,
        "submitted_at": application.submitted_at,
        "status_label": "Application submitted",
        "resume_filename": (
            application.resume_document.original_filename if application.resume_document else None
        ),
        "progress": [],
        "assessment": assessment,
        "intro_video": intro_video,
        "interview": None,
    }


def application_read_payload(application: Application) -> dict:
    latest_run = application.screening_runs[0] if application.screening_runs else None
    assessment = application_assessment_for_read(application, include_result=True)
    intro_video = getattr(application, "_intro_video_read", None)
    interview = getattr(application, "_interview_read", None)
    return {
        "id": application.id,
        "candidate_id": application.candidate_id,
        "job_id": application.job_id,
        "submitted_at": application.submitted_at,
        "resume_document_ref": application.resume_document_ref,
        "resume_document_id": application.resume_document_id,
        "applied_designation": application.applied_designation,
        "application_payload": application.application_payload,
        "current_stage": application.current_stage,
        "candidate": _candidate_read(application.candidate),
        "job_title": application.job.title,
        "job_department_id": application.job.department_id,
        "job_location": application.job.location,
        "screening_status": latest_run.run_status.value if latest_run else None,
        "screening_score": latest_run.score if latest_run else None,
        "screening_eligibility": latest_run.eligibility if latest_run else None,
        "evidence_completeness": latest_run.evidence_completeness if latest_run else None,
        "assessment_status": assessment["status"] if assessment else None,
        "assessment_score": (assessment.get("result") or {}).get("percentage") if assessment else None,
        "assessment_completed_at": (assessment.get("result") or {}).get("completed_at") if assessment else None,
        "intro_video_status": intro_video["status"] if intro_video else None,
        "interview_status": interview["status"] if interview else None,
    }


def load_application_followup_reads(db: Session, application: Application) -> None:
    application._intro_video_read = intro_video_read(intro_video_for_application(db, application))
    application._interview_read = interview_read(interview_for_application(db, application))


def application_assessment_for_read(application: Application, *, include_result: bool = False) -> dict | None:
    db = object_session(application)
    if db is None:
        return None
    assignment = application_assessment(db, application)
    return assessment_assignment_read(assignment, include_result=include_result)


def candidate_progress_rows(
    application: Application,
    *,
    assessment: dict | None,
    intro_video: dict | None,
    interview: dict | None,
) -> list[dict]:
    screening_complete = application.current_stage in {
        ApplicationStage.SCREENING_COMPLETE,
        ApplicationStage.SCREENING_REVIEW,
        ApplicationStage.SHORTLISTED_FOR_ASSESSMENT,
        ApplicationStage.SCREENING_HOLD,
        ApplicationStage.NOT_PROGRESSED_AFTER_SCREENING,
    }
    return [
        {"label": "Application submitted", "status": "complete"},
        {"label": "Application review", "status": "complete" if screening_complete else "in_progress"},
        {"label": "Assessment", "status": assessment["status"] if assessment else "not_assigned"},
        {"label": "Introduction video", "status": intro_video["status"] if intro_video else "not_requested"},
        {"label": "Interview", "status": interview["status"] if interview else "NOT_SCHEDULED"},
        {"label": "Decision", "status": _candidate_status_label(application.current_stage)},
    ]


def _validate_application_payload(job: Job, data: PublicApplicationCreate) -> None:
    basic = data.basic
    required_basic = [
        "full_name",
        "email",
        "phone",
        "date_of_birth",
        "gender",
        "mother_tongue",
        "previously_employed_with_mit_adt",
        "specialisation",
    ]
    missing = [field for field in required_basic if not str(basic.get(field, "")).strip()]
    if job.application_config.get("designation_options") and not (data.applied_designation or basic.get("designation")):
        missing.append("designation")
    if job.role_category == JobRoleCategory.FACULTY or job.application_config.get("requires_faculty_profile"):
        research = data.research
        qualifications = data.qualifications
        for field in ("phd_status", "published_research_papers"):
            if not str(research.get(field, "")).strip():
                missing.append(field)
        if not (qualifications.get("net") or qualifications.get("set") or research.get("phd_status")):
            missing.append("NET/SET/PhD qualification")
    if missing:
        raise InvalidTransition(f"Application is missing required fields: {', '.join(sorted(set(missing)))}")


def _candidate_read(candidate: Candidate) -> dict:
    return {
        "id": candidate.id,
        "user_id": candidate.user_id,
        "full_name": candidate.full_name,
        "email": candidate.email,
        "phone": candidate.phone,
        "education_profile": candidate.education_profile,
        "work_experience_profile": candidate.work_experience_profile,
        "resume_document_ref": candidate.resume_document_ref,
        "resume_document_id": candidate.resume_document_id,
    }


def _candidate_status_label(stage: ApplicationStage) -> str:
    if stage in {
        ApplicationStage.APPLICATION_RECEIVED,
        ApplicationStage.SCREENING_PENDING,
        ApplicationStage.SCREENING_RUNNING,
        ApplicationStage.SCREENING_COMPLETE,
        ApplicationStage.SCREENING_REVIEW,
        ApplicationStage.SCREENING_HOLD,
    }:
        return "Under Review"
    if stage == ApplicationStage.SHORTLISTED_FOR_ASSESSMENT:
        return "Assessment"
    if stage == ApplicationStage.NOT_PROGRESSED_AFTER_SCREENING:
        return "Closed"
    return "Application Received"
