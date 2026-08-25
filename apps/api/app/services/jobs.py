from app.core.errors import InvalidTransition, NotFound
from app.core.security import require_any_role
from app.db.base import utcnow
from app.models import (
    Department,
    DocumentPurpose,
    Job,
    JobReviewer,
    JobRubric,
    JobRubricVersion,
    JobStatus,
    Role,
    RubricVersionStatus,
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
from app.services.documents import get_document, store_upload
from app.services.rubric_utils import rubric_payload_hash
from fastapi import UploadFile
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
    if data.jd_document_id:
        _require_document_purpose(db, data.jd_document_id, DocumentPurpose.JOB_JD)
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
        jd_document_id=data.jd_document_id,
        role_category=data.role_category,
        application_config=data.application_config,
        intro_video_mode=data.intro_video_mode,
        assessment_template_version_id=data.assessment_template_version_id,
        source_reference=data.source_reference,
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
    if values.get("jd_document_id"):
        _require_document_purpose(db, values["jd_document_id"], DocumentPurpose.JOB_JD)
    reviewer_ids = values.pop("department_reviewer_ids", None)
    for key, value in values.items():
        setattr(job, key, value)
    if reviewer_ids is not None:
        job.reviewers = [JobReviewer(user_id=user_id) for user_id in reviewer_ids]
    record_audit(db, actor_id=actor.id, action="job.update_draft", entity_type="job", entity_id=job.id)
    return job


def attach_jd_document(db: Session, actor: User, job_id: str, file: UploadFile) -> Job:
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    job = get_job(db, job_id)
    if job.status != JobStatus.DRAFT:
        raise InvalidTransition("JD documents can only be replaced while a job is draft")
    document = store_upload(db, actor, file, DocumentPurpose.JOB_JD)
    job.jd_document_id = document.id
    job.jd_document_ref = None
    for rubric in job.rubrics:
        rubric.current_version_id = None
        for version in rubric.versions:
            if version.status in {
                RubricVersionStatus.DRAFT,
                RubricVersionStatus.PROPOSED,
            }:
                version.status = RubricVersionStatus.SUPERSEDED
    record_audit(
        db,
        actor_id=actor.id,
        action="job.jd_document_replace",
        entity_type="job",
        entity_id=job.id,
        remarks=f"JD document checksum {document.sha256}",
    )
    return job


def publish_job(db: Session, actor: User, job_id: str) -> Job:
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    job = get_job(db, job_id)
    if job.status != JobStatus.DRAFT:
        raise InvalidTransition("Only draft jobs can be published")
    rubric = job.rubrics[0] if job.rubrics else None
    approved_version = (
        db.get(JobRubricVersion, rubric.current_version_id) if rubric and rubric.current_version_id else None
    )
    if approved_version is None or approved_version.status != RubricVersionStatus.APPROVED:
        raise InvalidTransition("Jobs require an approved current rubric version before publication")
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
    source_document = get_document(db, data.source_jd_document_id) if data.source_jd_document_id else job.jd_document
    if source_document and source_document.purpose != DocumentPurpose.JOB_JD:
        raise InvalidTransition("Rubric versions must be based on a JD document")
    structured_payload = data.structured_jd_payload or {
        "schema_version": "structured-jd-v1",
        "job_id": job.id,
        "source_document_id": source_document.id if source_document else job.jd_document_ref or "unknown",
        "job_title": job.title,
        "department": job.department.name if job.department else "",
        "role_summary": job.description,
        "scoring_rubric": data.criteria,
    }
    version = JobRubricVersion(
        rubric=rubric,
        version_number=next_number,
        criteria=data.criteria,
        proposed_by=data.proposed_by,
        engine_mapping=data.engine_mapping,
        source_jd_document_id=source_document.id if source_document else None,
        source_jd_sha256=source_document.sha256 if source_document else None,
        source_structured_jd_schema_version=structured_payload.get("schema_version"),
        structured_jd_payload=structured_payload,
        status=RubricVersionStatus.DRAFT,
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


def _require_document_purpose(db: Session, document_id: str, purpose: DocumentPurpose):
    document = get_document(db, document_id)
    if document.purpose != purpose:
        raise InvalidTransition(f"Document must have purpose {purpose.value}")
    return document


def approve_rubric_version(db: Session, actor: User, version_id: str) -> JobRubricVersion:
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    version = db.get(JobRubricVersion, version_id)
    if version is None:
        raise NotFound("Rubric version not found")
    if version.status == RubricVersionStatus.APPROVED:
        return version
    if version.status == RubricVersionStatus.SUPERSEDED:
        raise InvalidTransition("Superseded rubric versions cannot be approved")
    job = version.rubric.job
    if job.jd_document_id and version.source_jd_document_id != job.jd_document_id:
        raise InvalidTransition("Rubric version must be regenerated from the current JD document before approval")
    version.status = RubricVersionStatus.APPROVED
    version.approved_by_id = actor.id
    version.approved_at = utcnow()
    version.approved_payload_sha256 = rubric_payload_hash(version)
    version.rubric.current_version_id = version.id
    record_audit(
        db,
        actor_id=actor.id,
        action="rubric.version_approve",
        entity_type="job_rubric_version",
        entity_id=version.id,
    )
    return version
