from app.core.errors import InvalidTransition, NotFound, PermissionDenied
from app.core.security import require_any_role, role_values
from app.db.base import utcnow
from app.models import Application, ApplicationStage, Candidate, DocumentPurpose, Job, JobStatus, Role, User
from app.schemas.applications import ApplicationCreate
from app.services.audit import record_audit
from app.services.documents import get_document
from app.services.workflow import transition_application
from sqlalchemy import select
from sqlalchemy.orm import Session


def submit_application(db: Session, actor: User, job_id: str, data: ApplicationCreate) -> Application:
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
    return application


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
    return {
        "id": application.id,
        "job_id": application.job_id,
        "job_title": application.job.title,
        "submitted_at": application.submitted_at,
        "status_label": _candidate_status_label(application.current_stage),
        "resume_filename": (
            application.resume_document.original_filename if application.resume_document else None
        ),
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
