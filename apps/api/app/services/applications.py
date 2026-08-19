from app.core.errors import InvalidTransition, NotFound, PermissionDenied
from app.core.security import require_any_role, role_values
from app.db.base import utcnow
from app.models import Application, ApplicationStage, Candidate, Job, JobStatus, Role, User
from app.schemas.applications import ApplicationCreate
from app.services.audit import record_audit
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
    if data.candidate.user_id:
        candidate = db.scalar(select(Candidate).where(Candidate.user_id == data.candidate.user_id))
    if candidate is None:
        candidate = Candidate(**data.candidate.model_dump())
        db.add(candidate)
        db.flush()
    elif candidate.user_id != actor.id:
        raise PermissionDenied("Candidate can only submit their own profile")

    application = Application(
        candidate=candidate,
        job=job,
        submitted_at=utcnow(),
        resume_document_ref=data.resume_document_ref or candidate.resume_document_ref,
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
        "current_stage": application.current_stage,
    }

