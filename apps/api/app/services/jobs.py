from app.core.errors import InvalidTransition, NotFound
from app.core.security import require_any_role
from app.db.base import utcnow
from app.models import (
    Department,
    Job,
    JobReviewer,
    JobRubric,
    JobRubricVersion,
    JobStatus,
    Role,
    School,
    User,
)
from app.schemas.jobs import (
    DepartmentCreate,
    JobCreate,
    JobUpdate,
    RubricVersionCreate,
    SchoolCreate,
)
from app.services.audit import record_audit
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

STAFF_JOB_ROLES = {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN}


def create_school(db: Session, data: SchoolCreate) -> School:
    school = School(name=data.name)
    db.add(school)
    db.flush()
    return school


def create_department(db: Session, data: DepartmentCreate) -> Department:
    department = Department(school_id=data.school_id, name=data.name)
    db.add(department)
    db.flush()
    return department


def create_job(db: Session, actor: User, data: JobCreate) -> Job:
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    job = Job(
        title=data.title,
        school_id=data.school_id,
        department_id=data.department_id,
        designation=data.designation,
        employment_type=data.employment_type,
        vacancy_count=data.vacancy_count,
        location=data.location,
        application_start=data.application_start,
        application_end=data.application_end,
        description=data.description,
        jd_document_ref=data.jd_document_ref,
        recruiter_id=data.recruiter_id,
        hiring_manager_id=data.hiring_manager_id,
    )
    job.reviewers = [JobReviewer(user_id=user_id) for user_id in data.department_reviewer_ids]
    job.rubrics = [JobRubric()]
    db.add(job)
    db.flush()
    record_audit(db, actor_id=actor.id, action="job.create", entity_type="job", entity_id=job.id)
    return job


def get_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFound("Job not found")
    return job


def list_jobs(
    db: Session,
    *,
    search: str | None = None,
    status: JobStatus | None = None,
    department_id: str | None = None,
    public_only: bool = False,
) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    conditions = []
    if search:
        needle = f"%{search}%"
        conditions.append(or_(Job.title.ilike(needle), Job.designation.ilike(needle), Job.location.ilike(needle)))
    if status:
        conditions.append(Job.status == status)
    if department_id:
        conditions.append(Job.department_id == department_id)
    if public_only:
        conditions.append(Job.status == JobStatus.PUBLISHED)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    return list(db.scalars(stmt))


def update_draft_job(db: Session, actor: User, job_id: str, data: JobUpdate) -> Job:
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    job = get_job(db, job_id)
    if job.status != JobStatus.DRAFT:
        raise InvalidTransition("Only draft jobs can be edited")
    values = data.model_dump(exclude_unset=True)
    reviewer_ids = values.pop("department_reviewer_ids", None)
    for key, value in values.items():
        setattr(job, key, value)
    if reviewer_ids is not None:
        job.reviewers = [JobReviewer(user_id=user_id) for user_id in reviewer_ids]
    record_audit(db, actor_id=actor.id, action="job.update_draft", entity_type="job", entity_id=job.id)
    return job


def publish_job(db: Session, actor: User, job_id: str) -> Job:
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    job = get_job(db, job_id)
    if job.status != JobStatus.DRAFT:
        raise InvalidTransition("Only draft jobs can be published")
    job.status = JobStatus.PUBLISHED
    record_audit(db, actor_id=actor.id, action="job.publish", entity_type="job", entity_id=job.id)
    return job


def close_job(db: Session, actor: User, job_id: str) -> Job:
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    job = get_job(db, job_id)
    if job.status != JobStatus.PUBLISHED:
        raise InvalidTransition("Only published jobs can be closed")
    job.status = JobStatus.CLOSED
    record_audit(db, actor_id=actor.id, action="job.close", entity_type="job", entity_id=job.id)
    return job


def add_rubric_version(
    db: Session, actor: User, job_id: str, data: RubricVersionCreate
) -> JobRubricVersion:
    require_any_role(actor, STAFF_JOB_ROLES)
    job = get_job(db, job_id)
    rubric = job.rubrics[0] if job.rubrics else JobRubric(job=job)
    next_number = (max((version.version_number for version in rubric.versions), default=0) + 1)
    version = JobRubricVersion(
        rubric=rubric,
        version_number=next_number,
        criteria=data.criteria,
        proposed_by=data.proposed_by,
        engine_mapping=data.engine_mapping,
    )
    db.add(version)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        action="rubric.version_create",
        entity_type="job_rubric_version",
        entity_id=version.id,
    )
    return version


def approve_rubric_version(db: Session, actor: User, version_id: str) -> JobRubricVersion:
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    version = db.get(JobRubricVersion, version_id)
    if version is None:
        raise NotFound("Rubric version not found")
    if version.status == "approved":
        return version
    version.status = "approved"
    version.approved_by_id = actor.id
    version.approved_at = utcnow()
    version.rubric.current_version_id = version.id
    record_audit(
        db,
        actor_id=actor.id,
        action="rubric.version_approve",
        entity_type="job_rubric_version",
        entity_id=version.id,
    )
    return version

