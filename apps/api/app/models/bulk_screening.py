import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class BulkScreeningSourceType(str, enum.Enum):
    EXISTING_JOB = "EXISTING_JOB"
    ADHOC_JD = "ADHOC_JD"


class BulkScreeningBatchStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BulkScreeningItemStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"
    UNSUPPORTED = "UNSUPPORTED"


class BulkScreeningClassification(str, enum.Enum):
    MEETS_CRITERIA = "MEETS_CRITERIA"
    DOES_NOT_MEET_CRITERIA = "DOES_NOT_MEET_CRITERIA"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class BulkScreeningBatch(Base, TimestampMixin):
    __tablename__ = "bulk_screening_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source_type: Mapped[BulkScreeningSourceType] = mapped_column(
        Enum(BulkScreeningSourceType, name="bulk_screening_source_type"), nullable=False, index=True
    )
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    rubric_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_rubric_versions.id"), nullable=True, index=True
    )
    ad_hoc_jd_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    ad_hoc_structured_jd: Mapped[dict | None] = mapped_column(JSON)
    ad_hoc_structured_jd_sha256: Mapped[str | None] = mapped_column(String(64))
    criteria_snapshot: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    target_designation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    criteria_confirmed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    criteria_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[BulkScreeningBatchStatus] = mapped_column(
        Enum(BulkScreeningBatchStatus, name="bulk_screening_batch_status"),
        nullable=False,
        default=BulkScreeningBatchStatus.DRAFT,
        index=True,
    )
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unsupported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    archived_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    created_by = relationship("User", foreign_keys=[created_by_id])
    criteria_confirmed_by = relationship("User", foreign_keys=[criteria_confirmed_by_id])
    archived_by = relationship("User", foreign_keys=[archived_by_id])
    job = relationship("Job")
    rubric_version = relationship("JobRubricVersion")
    ad_hoc_jd_document = relationship("Document", foreign_keys=[ad_hoc_jd_document_id])
    items: Mapped[list["BulkScreeningItem"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="BulkScreeningItem.created_at"
    )


class BulkScreeningItem(Base, TimestampMixin):
    __tablename__ = "bulk_screening_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    batch_id: Mapped[str] = mapped_column(ForeignKey("bulk_screening_batches.id"), nullable=False, index=True)
    resume_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    duplicate_of_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("bulk_screening_items.id"), nullable=True, index=True
    )
    status: Mapped[BulkScreeningItemStatus] = mapped_column(
        Enum(BulkScreeningItemStatus, name="bulk_screening_item_status"),
        nullable=False,
        default=BulkScreeningItemStatus.PENDING,
        index=True,
    )
    processing_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    classification: Mapped[BulkScreeningClassification | None] = mapped_column(
        Enum(BulkScreeningClassification, name="bulk_screening_classification"), nullable=True, index=True
    )
    concise_reason: Mapped[str | None] = mapped_column(Text)
    candidate_name: Mapped[str | None] = mapped_column(String(240))
    provider: Mapped[str | None] = mapped_column(String(100))
    provider_engine_version: Mapped[str | None] = mapped_column(String(100))
    engine_contract_version: Mapped[str | None] = mapped_column(String(80))
    engine_artifact_schema_version: Mapped[str | None] = mapped_column(String(80))
    engine_code_version: Mapped[str | None] = mapped_column(String(120))
    model_endpoint_slot: Mapped[str | None] = mapped_column(String(30))
    eligibility: Mapped[str | None] = mapped_column(String(30))
    evidence_completeness: Mapped[float | None] = mapped_column(Float)
    confirmed_experience_months: Mapped[int | None] = mapped_column(Integer)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(Text)
    raw_result_ref: Mapped[str | None] = mapped_column(String(500))
    raw_result: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch: Mapped[BulkScreeningBatch] = relationship(back_populates="items")
    resume_document = relationship("Document", foreign_keys=[resume_document_id])
    duplicate_of = relationship("BulkScreeningItem", remote_side=[id])
    criterion_results: Mapped[list["BulkScreeningCriterionResult"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="BulkScreeningCriterionResult.created_at"
    )
    work_item: Mapped["BulkScreeningWorkItem | None"] = relationship(back_populates="item", uselist=False)


class BulkScreeningCriterionResult(Base, TimestampMixin):
    __tablename__ = "bulk_screening_criterion_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    item_id: Mapped[str] = mapped_column(ForeignKey("bulk_screening_items.id"), nullable=False, index=True)
    criterion_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    criterion_name: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    candidate_requirement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_found: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_information: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    ambiguity: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    verification_needed: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    unmatched_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    raw_component_assessment: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    item: Mapped[BulkScreeningItem] = relationship(back_populates="criterion_results")
    evidence: Mapped[list["BulkScreeningEvidence"]] = relationship(
        back_populates="criterion_result", cascade="all, delete-orphan", order_by="BulkScreeningEvidence.created_at"
    )


class BulkScreeningEvidence(Base, TimestampMixin):
    __tablename__ = "bulk_screening_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    criterion_result_id: Mapped[str] = mapped_column(
        ForeignKey("bulk_screening_criterion_results.id"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(200), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    block_index: Mapped[int | None] = mapped_column(Integer)
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    criterion_result: Mapped[BulkScreeningCriterionResult] = relationship(back_populates="evidence")


class BulkScreeningWorkItem(Base, TimestampMixin):
    __tablename__ = "bulk_screening_work_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    item_id: Mapped[str] = mapped_column(ForeignKey("bulk_screening_items.id"), nullable=False, unique=True)
    status: Mapped[BulkScreeningItemStatus] = mapped_column(
        Enum(BulkScreeningItemStatus, name="bulk_screening_item_status"),
        nullable=False,
        default=BulkScreeningItemStatus.PENDING,
        index=True,
    )
    processing_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(Text)

    item: Mapped[BulkScreeningItem] = relationship(back_populates="work_item")
