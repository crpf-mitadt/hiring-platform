import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ScreeningRunStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ScreeningRun(Base, TimestampMixin):
    __tablename__ = "screening_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    rubric_version_id: Mapped[str | None] = mapped_column(ForeignKey("job_rubric_versions.id"), index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_engine_version: Mapped[str] = mapped_column(String(100), nullable=False)
    run_status: Mapped[ScreeningRunStatus] = mapped_column(
        Enum(ScreeningRunStatus, name="screening_run_status"),
        default=ScreeningRunStatus.QUEUED,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eligibility: Mapped[str | None] = mapped_column(String(30))
    score: Mapped[float | None] = mapped_column(Float)
    evidence_completeness: Mapped[float | None] = mapped_column(Float)
    confirmed_experience_months: Mapped[int | None] = mapped_column(Integer)
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    raw_result_ref: Mapped[str | None] = mapped_column(String(500))
    raw_result: Mapped[dict | None] = mapped_column(JSON)

    application = relationship("Application")
    rubric_version = relationship("JobRubricVersion")
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
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    match_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    weighted_score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    missing_information: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
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

