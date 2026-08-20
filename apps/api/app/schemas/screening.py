from datetime import datetime

from app.models import ApplicationStage, HiringDecisionType, ScreeningJobStatus, ScreeningRunStatus
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
    weight: float | None
    requirement_ids: list[str]
    status: str
    match_fraction: float
    weighted_score: float
    explanation: str
    candidate_requirement: str
    evidence_found: list[str]
    missing_information: list[str]
    ambiguity: list[str]
    verification_needed: list[str]
    matched_terms: list[str]
    unmatched_terms: list[str]
    raw_component_assessment: dict
    evidence: list[ScreeningEvidenceRead]


class ScreeningRunRead(ApiModel):
    id: str
    application_id: str
    rubric_version_id: str | None
    jd_document_sha256: str | None
    resume_document_sha256: str | None
    provider: str
    provider_engine_version: str
    engine_contract_version: str | None
    engine_artifact_schema_version: str | None
    engine_code_version: str | None
    model_endpoint_slot: str | None
    structured_jd_sha256: str | None
    structured_resume_sha256: str | None
    run_status: ScreeningRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    attempt_count: int
    eligibility: str | None
    score: float | None
    score_before_gates: float | None
    maximum_score: float | None
    evidence_completeness: float | None
    confirmed_experience_months: int | None
    uncertain_experience_ranges: list[dict]
    mandatory_requirement_results: list[dict]
    human_review_required: bool | None
    recommendation_label: str | None
    strengths: list[str]
    gaps: list[str]
    warnings: list[str]
    raw_result_ref: str | None
    criterion_results: list[ScreeningCriterionResultRead]


class ScreeningJobRead(ApiModel):
    id: str
    screening_run_id: str
    status: ScreeningJobStatus
    attempts: int
    max_attempts: int
    locked_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    screening_run: ScreeningRunRead


class StageHistoryDossierRead(ApiModel):
    id: str
    previous_stage: ApplicationStage | None
    new_stage: ApplicationStage
    actor_id: str
    timestamp: datetime
    remarks: str | None


class HiringDecisionDossierRead(ApiModel):
    id: str
    decision: HiringDecisionType
    actor_id: str
    timestamp: datetime
    remarks: str


class ScreeningDossierRead(ApiModel):
    application_id: str
    current_stage: ApplicationStage
    screening_runs: list[ScreeningRunRead]
    stage_history: list[StageHistoryDossierRead]
    decisions: list[HiringDecisionDossierRead]
