from datetime import datetime

from app.models import JobStatus
from app.schemas.common import ApiModel


class SchoolCreate(ApiModel):
    name: str


class DepartmentCreate(ApiModel):
    school_id: str
    name: str


class SchoolRead(ApiModel):
    id: str
    name: str


class DepartmentRead(ApiModel):
    id: str
    school_id: str
    name: str


class JobBase(ApiModel):
    title: str
    school_id: str
    department_id: str
    designation: str
    employment_type: str
    vacancy_count: int = 1
    location: str
    application_start: datetime | None = None
    application_end: datetime | None = None
    description: str = ""
    jd_document_ref: str | None = None
    recruiter_id: str
    hiring_manager_id: str
    department_reviewer_ids: list[str] = []


class JobCreate(JobBase):
    pass


class JobUpdate(ApiModel):
    title: str | None = None
    designation: str | None = None
    employment_type: str | None = None
    vacancy_count: int | None = None
    location: str | None = None
    application_start: datetime | None = None
    application_end: datetime | None = None
    description: str | None = None
    jd_document_ref: str | None = None
    hiring_manager_id: str | None = None
    department_reviewer_ids: list[str] | None = None


class JobRead(JobBase):
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime


class RubricVersionCreate(ApiModel):
    criteria: list[dict]
    proposed_by: str = "human"
    engine_mapping: dict = {}


class RubricVersionRead(ApiModel):
    id: str
    rubric_id: str
    version_number: int
    status: str
    proposed_by: str
    approved_by_id: str | None
    approved_at: datetime | None
    criteria: list[dict]
    engine_mapping: dict

