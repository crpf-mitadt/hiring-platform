from datetime import datetime

from app.models import ApplicationStage
from app.schemas.common import ApiModel
from pydantic import EmailStr


class CandidateCreate(ApiModel):
    user_id: str | None = None
    full_name: str
    email: EmailStr
    phone: str | None = None
    education_profile: dict = {}
    work_experience_profile: dict = {}
    resume_document_ref: str | None = None


class CandidateRead(ApiModel):
    id: str
    user_id: str | None
    full_name: str
    email: EmailStr
    phone: str | None
    education_profile: dict
    work_experience_profile: dict
    resume_document_ref: str | None


class ApplicationCreate(ApiModel):
    candidate: CandidateCreate
    resume_document_ref: str | None = None


class ApplicationRead(ApiModel):
    id: str
    candidate_id: str
    job_id: str
    submitted_at: datetime
    resume_document_ref: str | None
    current_stage: ApplicationStage


class CandidateApplicationStatus(ApiModel):
    id: str
    job_id: str
    job_title: str
    submitted_at: datetime
    current_stage: ApplicationStage


class ApplicationTransitionRequest(ApiModel):
    remarks: str | None = None


class StageHistoryRead(ApiModel):
    id: str
    application_id: str
    previous_stage: ApplicationStage | None
    new_stage: ApplicationStage
    actor_id: str
    timestamp: datetime
    remarks: str | None

