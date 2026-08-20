import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ScreeningRunStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScreeningJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScreeningRun(Base, TimestampMixin):
    __tablename__ = "screening_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    rubric_version_id: Mapped[str | None] = mapped_column(ForeignKey("job_rubric_versions.id"), index=True)
    retry_of_run_id: Mapped[str | None] = mapped_column(ForeignKey("screening_runs.id"), nullable=True, index=True)
    jd_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    jd_document_sha256: Mapped[str | None] = mapped_column(String(64))
    resume_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    resume_document_sha256: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_contract_version: Mapped[str | None] = mapped_column(String(80))
    engine_artifact_schema_version: Mapped[str | None] = mapped_column(String(80))
    engine_code_version: Mapped[str | None] = mapped_column(String(120))
    model_endpoint_slot: Mapped[str | None] = mapped_column(String(30))
    structured_jd_sha256: Mapped[str | None] = mapped_column(String(64))
    structured_resume_sha256: Mapped[str | None] = mapped_column(String(64))
    run_status: Mapped[ScreeningRunStatus] = mapped_column(
        Enum(ScreeningRunStatus, name="screening_run_status"),
        default=ScreeningRunStatus.QUEUED,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eligibility: Mapped[str | None] = mapped_column(String(30))
    score: Mapped[float | None] = mapped_column(Float)
    score_before_gates: Mapped[float | None] = mapped_column(Float)
    maximum_score: Mapped[float | None] = mapped_column(Float)
    evidence_completeness: Mapped[float | None] = mapped_column(Float)
    confirmed_experience_months: Mapped[int | None] = mapped_column(Integer)
    uncertain_experience_ranges: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    mandatory_requirement_results: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    human_review_required: Mapped[bool | None] = mapped_column(default=True)
    recommendation_label: Mapped[str | None] = mapped_column(String(100))
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    raw_result_ref: Mapped[str | None] = mapped_column(String(500))
    raw_result: Mapped[dict | None] = mapped_column(JSON)

    application = relationship("Application")
    rubric_version = relationship("JobRubricVersion")
    retry_of_run = relationship("ScreeningRun", remote_side=[id])
    jd_document = relationship("Document", foreign_keys=[jd_document_id])
    resume_document = relationship("Document", foreign_keys=[resume_document_id])
    criterion_results: Mapped[list["ScreeningCriterionResult"]] = relationship(
        back_populates="screening_run", cascade="all, delete-orphan", lazy="selectin"
    )


class ScreeningCriterionResult(Base):
    __tablename__ = "screening_criterion_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    screening_run_id: Mapped[str] = mapped_column(ForeignKey("screening_runs.id"), nullable=False, index=True)
    criterion_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    criterion_name: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    weight: Mapped[float | None] = mapped_column(Float)
    requirement_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    match_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    weighted_score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_requirement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_found: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_information: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    ambiguity: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    verification_needed: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    unmatched_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    raw_component_assessment: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    screening_run: Mapped[ScreeningRun] = relationship(back_populates="criterion_results")
    evidence: Mapped[list["ScreeningEvidence"]] = relationship(
        back_populates="criterion_result", cascade="all, delete-orphan", lazy="selectin"
    )


class ScreeningEvidence(Base):
    __tablename__ = "screening_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    criterion_result_id: Mapped[str] = mapped_column(
        ForeignKey("screening_criterion_results.id"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(200), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    block_index: Mapped[int | None] = mapped_column(Integer)
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    criterion_result: Mapped[ScreeningCriterionResult] = relationship(back_populates="evidence")


class ScreeningJob(Base, TimestampMixin):
    __tablename__ = "screening_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    screening_run_id: Mapped[str] = mapped_column(ForeignKey("screening_runs.id"), nullable=False, unique=True)
    status: Mapped[ScreeningJobStatus] = mapped_column(
        Enum(ScreeningJobStatus, name="screening_job_status"),
        nullable=False,
        default=ScreeningJobStatus.PENDING,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(Text)

    screening_run = relationship("ScreeningRun")
