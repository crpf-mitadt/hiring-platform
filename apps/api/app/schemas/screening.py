from datetime import datetime

from app.models import ScreeningRunStatus
from app.schemas.common import ApiModel


class ScreeningEvidenceRead(ApiModel):
    id: str
    source_type: str
    source_document_id: str
    page_number: int | None
    block_index: int | None
    exact_text: str
    normalized_text: str | None
    evidence_status: str
    notes: str | None


class ScreeningCriterionResultRead(ApiModel):
    id: str
    criterion_id: str
    criterion_name: str
    category: str
    status: str
    match_fraction: float
    weighted_score: float
    explanation: str
    missing_information: list[str]
    raw_component_assessment: dict
    evidence: list[ScreeningEvidenceRead]


class ScreeningRunRead(ApiModel):
    id: str
    application_id: str
    rubric_version_id: str | None
    provider: str
    provider_engine_version: str
    run_status: ScreeningRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    eligibility: str | None
    score: float | None
    evidence_completeness: float | None
    confirmed_experience_months: int | None
    strengths: list[str]
    gaps: list[str]
    warnings: list[str]
    raw_result_ref: str | None
    criterion_results: list[ScreeningCriterionResultRead]

