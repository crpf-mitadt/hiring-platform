from fastapi import APIRouter

from app.api.deps import ActorDep, DbDep
from app.models import JobStatus
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
    close_job,
    create_department,
    create_job,
    create_school,
    get_job,
    list_jobs,
    publish_job,
    update_draft_job,
)

router = APIRouter(tags=["jobs"])


def job_to_read(job) -> dict:
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
        "recruiter_id": job.recruiter_id,
        "hiring_manager_id": job.hiring_manager_id,
        "department_reviewer_ids": [reviewer.user_id for reviewer in job.reviewers],
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.post("/schools", response_model=SchoolRead)
def api_create_school(db: DbDep, data: SchoolCreate):
    school = create_school(db, data)
    db.commit()
    return school


@router.post("/departments", response_model=DepartmentRead)
def api_create_department(db: DbDep, data: DepartmentCreate):
    department = create_department(db, data)
    db.commit()
    return department


@router.post("/jobs", response_model=JobRead)
def api_create_job(db: DbDep, actor: ActorDep, data: JobCreate) -> dict:
    job = create_job(db, actor, data)
    db.commit()
    return job_to_read(job)


@router.get("/jobs", response_model=list[JobRead])
def api_list_jobs(
    db: DbDep,
    search: str | None = None,
    status: JobStatus | None = None,
    department_id: str | None = None,
) -> list[dict]:
    return [job_to_read(job) for job in list_jobs(db, search=search, status=status, department_id=department_id)]


@router.get("/public/jobs", response_model=list[JobRead])
def api_public_jobs(db: DbDep, search: str | None = None) -> list[dict]:
    return [job_to_read(job) for job in list_jobs(db, search=search, public_only=True)]


@router.get("/jobs/{job_id}", response_model=JobRead)
def api_read_job(db: DbDep, job_id: str) -> dict:
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


@router.post("/rubric-versions/{version_id}/approve", response_model=RubricVersionRead)
def api_approve_rubric_version(db: DbDep, actor: ActorDep, version_id: str):
    version = approve_rubric_version(db, actor, version_id)
    db.commit()
    return version
