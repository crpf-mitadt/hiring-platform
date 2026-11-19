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
    resume_document_id: str | None = None


class CandidateRead(ApiModel):
    id: str
    user_id: str | None
    full_name: str
    email: EmailStr
    phone: str | None
    education_profile: dict
    work_experience_profile: dict
    resume_document_ref: str | None
    resume_document_id: str | None


class ApplicationCreate(ApiModel):
    candidate: CandidateCreate
    resume_document_ref: str | None = None
    resume_document_id: str | None = None


class PublicApplicationCreate(ApiModel):
    basic: dict
    education: dict
    experience: dict
    research: dict = {}
    qualifications: dict = {}
    languages: dict = {}
    documents: dict = {}
    resume_document_id: str
    photo_document_id: str
    applied_designation: str | None = None


class PublicApplicationSubmitRead(ApiModel):
    id: str
    job_id: str
    job_title: str
    submitted_at: datetime
    status_label: str
    continuation_url: str | None = None


class ApplicationAccessExchangeRequest(ApiModel):
    token: str


class ApplicationRead(ApiModel):
    id: str
    candidate_id: str
    job_id: str
    submitted_at: datetime
    resume_document_ref: str | None
    resume_document_id: str | None
    applied_designation: str | None = None
    application_payload: dict = {}
    current_stage: ApplicationStage
    candidate: CandidateRead | None = None
    job_title: str | None = None
    job_department_id: str | None = None
    job_location: str | None = None
    screening_status: str | None = None
    screening_score: float | None = None
    screening_eligibility: str | None = None
    evidence_completeness: float | None = None
    assessment_status: str | None = None
    assessment_score: float | None = None
    assessment_completed_at: datetime | None = None
    intro_video_status: str | None = None
    interview_status: str | None = None


class CandidateApplicationStatus(ApiModel):
    id: str
    job_id: str
    job_title: str
    submitted_at: datetime
    status_label: str
    resume_filename: str | None = None
    progress: list[dict] = []
    assessment: dict | None = None
    intro_video: dict | None = None
    interview: dict | None = None


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
