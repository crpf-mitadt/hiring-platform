from datetime import datetime

from app.models import (
    BulkScreeningBatchStatus,
    BulkScreeningClassification,
    BulkScreeningItemStatus,
    BulkScreeningSourceType,
)
from app.schemas.common import ApiModel
from app.schemas.documents import DocumentRead


class BulkSupportedFormatsRead(ApiModel):
    jd: list[str]
    resumes: list[str]
    archives: list[str]
    unsupported: list[str]
    notes: list[str]


class BulkCriteriaConfirmRequest(ApiModel):
    confirmed: bool = True
    target_designation: str | None = None


class BulkScreeningEvidenceRead(ApiModel):
    id: str
    source_type: str
    source_document_id: str
    page_number: int | None
    block_index: int | None
    exact_text: str
    normalized_text: str | None
    evidence_status: str
    notes: str | None


class BulkScreeningCriterionResultRead(ApiModel):
    id: str
    criterion_id: str
    criterion_name: str
    category: str
    status: str
    explanation: str
    candidate_requirement: str
    evidence_found: list[str]
    missing_information: list[str]
    ambiguity: list[str]
    verification_needed: list[str]
    matched_terms: list[str]
    unmatched_terms: list[str]
    raw_component_assessment: dict
    evidence: list[BulkScreeningEvidenceRead]


class BulkScreeningItemRead(ApiModel):
    id: str
    batch_id: str
    resume_document_id: str | None
    original_filename: str
    content_sha256: str | None
    duplicate_of_item_id: str | None
    status: BulkScreeningItemStatus
    processing_stage: str | None
    progress_percent: int
    stage_updated_at: datetime | None
    classification: BulkScreeningClassification | None
    concise_reason: str | None
    candidate_name: str | None
    provider: str | None
    provider_engine_version: str | None
    engine_contract_version: str | None
    engine_artifact_schema_version: str | None
    engine_code_version: str | None
    model_endpoint_slot: str | None
    eligibility: str | None
    evidence_completeness: float | None
    confirmed_experience_months: int | None
    warnings: list[str]
    failure_code: str | None
    failure_message: str | None
    raw_result_ref: str | None
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    criterion_results: list[BulkScreeningCriterionResultRead] = []


class BulkScreeningBatchRead(ApiModel):
    id: str
    created_by_id: str
    source_type: BulkScreeningSourceType
    job_id: str | None
    rubric_version_id: str | None
    ad_hoc_jd_document_id: str | None
    ad_hoc_structured_jd: dict | None
    ad_hoc_structured_jd_sha256: str | None
    criteria_snapshot: list[dict]
    target_designation: str | None
    criteria_confirmed_by_id: str | None
    criteria_confirmed_at: datetime | None
    title: str
    status: BulkScreeningBatchStatus
    total_files: int
    accepted_count: int
    duplicate_count: int
    unsupported_count: int
    completed_count: int
    failed_count: int
    progress_percent: int
    failure_code: str | None
    failure_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    archived_at: datetime | None
    archived_by_id: str | None
    created_at: datetime
    updated_at: datetime
    items: list[BulkScreeningItemRead] = []
    jd_document: DocumentRead | None = None
    job_title: str | None = None


class BulkScreeningBatchSummaryRead(ApiModel):
    id: str
    source_type: BulkScreeningSourceType
    job_id: str | None
    rubric_version_id: str | None
    target_designation: str | None
    title: str
    status: BulkScreeningBatchStatus
    total_files: int
    accepted_count: int
    duplicate_count: int
    unsupported_count: int
    completed_count: int
    failed_count: int
    progress_percent: int
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    completed_at: datetime | None
    archived_at: datetime | None
    archived_by_id: str | None
    job_title: str | None = None
