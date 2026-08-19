import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class JobStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"


class ApplicationStage(str, enum.Enum):
    APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
    SCREENING_PENDING = "SCREENING_PENDING"
    SCREENING_RUNNING = "SCREENING_RUNNING"
    SCREENING_COMPLETE = "SCREENING_COMPLETE"
    SCREENING_REVIEW = "SCREENING_REVIEW"
    SHORTLISTED_FOR_ASSESSMENT = "SHORTLISTED_FOR_ASSESSMENT"
    SCREENING_HOLD = "SCREENING_HOLD"
    NOT_PROGRESSED_AFTER_SCREENING = "NOT_PROGRESSED_AFTER_SCREENING"


class HiringDecisionType(str, enum.Enum):
    SELECTED = "selected"
    NOT_SELECTED = "not_selected"
    HOLD = "hold"
    ANOTHER_ROUND = "another_round"


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), nullable=False, index=True)
    designation: Mapped[str] = mapped_column(String(200), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    vacancy_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    application_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    application_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    jd_document_ref: Mapped[str | None] = mapped_column(String(500))
    recruiter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    hiring_manager_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.DRAFT, nullable=False, index=True
    )

    school = relationship("School")
    department = relationship("Department")
    recruiter = relationship("User", foreign_keys=[recruiter_id])
    hiring_manager = relationship("User", foreign_keys=[hiring_manager_id])
    reviewers: Mapped[list["JobReviewer"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )
    rubrics: Mapped[list["JobRubric"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobReviewer(Base):
    __tablename__ = "job_reviewers"
    __table_args__ = (UniqueConstraint("job_id", "user_id", name="uq_job_reviewers_job_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    job: Mapped[Job] = relationship(back_populates="reviewers")
    user = relationship("User")


class JobRubric(Base, TimestampMixin):
    __tablename__ = "job_rubrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    job: Mapped[Job] = relationship(back_populates="rubrics")
    versions: Mapped[list["JobRubricVersion"]] = relationship(
        back_populates="rubric", cascade="all, delete-orphan", order_by="JobRubricVersion.version_number"
    )


class JobRubricVersion(Base, TimestampMixin):
    __tablename__ = "job_rubric_versions"
    __table_args__ = (UniqueConstraint("rubric_id", "version_number", name="uq_rubric_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    rubric_id: Mapped[str] = mapped_column(ForeignKey("job_rubrics.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    proposed_by: Mapped[str] = mapped_column(String(30), nullable=False, default="human")
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criteria: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    engine_mapping: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    rubric: Mapped[JobRubric] = relationship(back_populates="versions")
    approved_by = relationship("User")


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    education_profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    work_experience_profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resume_document_ref: Mapped[str | None] = mapped_column(String(500))

    user = relationship("User")
    applications: Mapped[list["Application"]] = relationship(back_populates="candidate")


class Application(Base, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job_application"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resume_document_ref: Mapped[str | None] = mapped_column(String(500))
    current_stage: Mapped[ApplicationStage] = mapped_column(
        Enum(ApplicationStage, name="application_stage"),
        default=ApplicationStage.APPLICATION_RECEIVED,
        nullable=False,
        index=True,
    )

    candidate: Mapped[Candidate] = relationship(back_populates="applications")
    job: Mapped[Job] = relationship()
    stage_history: Mapped[list["ApplicationStageHistory"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="ApplicationStageHistory.timestamp"
    )


class ApplicationStageHistory(Base):
    __tablename__ = "application_stage_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    previous_stage: Mapped[ApplicationStage | None] = mapped_column(
        Enum(ApplicationStage, name="application_stage")
    )
    new_stage: Mapped[ApplicationStage] = mapped_column(Enum(ApplicationStage, name="application_stage"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text)

    application: Mapped[Application] = relationship(back_populates="stage_history")
    actor = relationship("User")


class HiringDecision(Base):
    __tablename__ = "hiring_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    decision: Mapped[HiringDecisionType] = mapped_column(Enum(HiringDecisionType, name="hiring_decision_type"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remarks: Mapped[str] = mapped_column(Text, nullable=False)

    application: Mapped[Application] = relationship()
    actor = relationship("User")

