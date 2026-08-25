from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from sqlalchemy import select

from app.api.deps import ActorDep, DbDep
from app.core.config import get_settings
from app.core.errors import NotFound
from app.core.security import require_any_role
from app.models import JobRubric, JobRubricVersion, JobStatus, Role
from app.schemas.jobs import (
    DepartmentCreate,
    DepartmentRead,
    JobCreate,
    JobRead,
    JobUpdate,
    RubricVersionCreate,
    RubricVersionRead,
    SchoolCreate,
    SchoolRead,
)
from app.services.jobs import (
    add_rubric_version,
    approve_rubric_version,
    attach_jd_document,
    close_job,
    create_department,
    create_job,
    create_school,
    get_job,
    list_jobs,
    publish_job,
    update_draft_job,
)
from app.services.rubrics import (
    HiringScreeningEngineRubricProvider,
    MockRubricProvider,
    generate_rubric_version,
)

router = APIRouter(tags=["jobs"])


def job_to_read(job) -> dict:
    document = job.jd_document
    return {
        "id": job.id,
        "title": job.title,
        "school_id": job.school_id,
        "department_id": job.department_id,
        "designation": job.designation,
        "employment_type": job.employment_type,
        "vacancy_count": job.vacancy_count,
        "location": job.location,
        "application_start": job.application_start,
        "application_end": job.application_end,
        "description": job.description,
        "jd_document_ref": job.jd_document_ref,
        "jd_document_id": job.jd_document_id,
        "jd_document": document,
        "role_category": job.role_category,
        "application_config": job.application_config,
        "intro_video_mode": job.intro_video_mode,
        "assessment_template_version_id": job.assessment_template_version_id,
        "source_reference": job.source_reference,
        "recruiter_id": job.recruiter_id,
        "hiring_manager_id": job.hiring_manager_id,
        "department_reviewer_ids": [reviewer.user_id for reviewer in job.reviewers],
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.post("/schools", response_model=SchoolRead)
def api_create_school(db: DbDep, actor: ActorDep, data: SchoolCreate):
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    school = create_school(db, data)
    db.commit()
    return school


@router.post("/departments", response_model=DepartmentRead)
def api_create_department(db: DbDep, actor: ActorDep, data: DepartmentCreate):
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    department = create_department(db, data)
    db.commit()
    return department


@router.post("/jobs", response_model=JobRead)
def api_create_job(db: DbDep, actor: ActorDep, data: JobCreate) -> dict:
    job = create_job(db, actor, data)
    db.commit()
    return job_to_read(job)


@router.post("/jobs/{job_id}/jd-document", response_model=JobRead)
def api_upload_job_jd(db: DbDep, actor: ActorDep, job_id: str, file: Annotated[UploadFile, File()]) -> dict:
    job = attach_jd_document(db, actor, job_id, file)
    db.commit()
    return job_to_read(job)


@router.get("/jobs", response_model=list[JobRead])
def api_list_jobs(
    db: DbDep,
    actor: ActorDep,
    search: str | None = None,
    status: JobStatus | None = None,
    department_id: str | None = None,
) -> list[dict]:
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    return [job_to_read(job) for job in list_jobs(db, search=search, status=status, department_id=department_id)]


@router.get("/public/jobs", response_model=list[JobRead])
def api_public_jobs(db: DbDep, search: str | None = None) -> list[dict]:
    return [job_to_read(job) for job in list_jobs(db, search=search, public_only=True)]


@router.get("/public/jobs/{job_id}", response_model=JobRead)
def api_public_job_detail(db: DbDep, job_id: str) -> dict:
    job = get_job(db, job_id)
    if job.status != JobStatus.PUBLISHED:
        raise NotFound("Job not found")
    return job_to_read(job)


@router.get("/jobs/{job_id}", response_model=JobRead)
def api_read_job(db: DbDep, actor: ActorDep, job_id: str) -> dict:
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    return job_to_read(get_job(db, job_id))


@router.patch("/jobs/{job_id}", response_model=JobRead)
def api_update_job(db: DbDep, actor: ActorDep, job_id: str, data: JobUpdate) -> dict:
    job = update_draft_job(db, actor, job_id, data)
    db.commit()
    return job_to_read(job)


@router.post("/jobs/{job_id}/publish", response_model=JobRead)
def api_publish_job(db: DbDep, actor: ActorDep, job_id: str) -> dict:
    job = publish_job(db, actor, job_id)
    db.commit()
    return job_to_read(job)


@router.post("/jobs/{job_id}/close", response_model=JobRead)
def api_close_job(db: DbDep, actor: ActorDep, job_id: str) -> dict:
    job = close_job(db, actor, job_id)
    db.commit()
    return job_to_read(job)


@router.post("/jobs/{job_id}/rubric-versions", response_model=RubricVersionRead)
def api_create_rubric_version(db: DbDep, actor: ActorDep, job_id: str, data: RubricVersionCreate):
    version = add_rubric_version(db, actor, job_id, data)
    db.commit()
    return version


@router.get("/jobs/{job_id}/rubric-versions", response_model=list[RubricVersionRead])
def api_list_rubric_versions(db: DbDep, actor: ActorDep, job_id: str):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    get_job(db, job_id)
    return list(
        db.scalars(
            select(JobRubricVersion)
            .join(JobRubricVersion.rubric)
            .where(JobRubric.job_id == job_id)
            .order_by(JobRubricVersion.version_number.desc())
        )
    )


@router.post("/jobs/{job_id}/generate-rubric", response_model=RubricVersionRead)
def api_generate_rubric_version(db: DbDep, actor: ActorDep, job_id: str):
    settings = get_settings()
    job = get_job(db, job_id)
    provider = (
        HiringScreeningEngineRubricProvider()
        if settings.screening_provider == "engine"
        else MockRubricProvider()
    )
    version = generate_rubric_version(db, actor, job, provider=provider)
    db.commit()
    return version


@router.post("/rubric-versions/{version_id}/approve", response_model=RubricVersionRead)
def api_approve_rubric_version(db: DbDep, actor: ActorDep, version_id: str):
    version = approve_rubric_version(db, actor, version_id)
    db.commit()
    return version
