import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AssessmentTemplateStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"


class AssessmentQuestionType(str, enum.Enum):
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"


class AssessmentAssignmentStatus(str, enum.Enum):
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"


class AssessmentAttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"


class AssessmentTemplate(Base, TimestampMixin):
    __tablename__ = "assessment_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    versions: Mapped[list["AssessmentTemplateVersion"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="AssessmentTemplateVersion.version_number"
    )
    created_by = relationship("User")


class AssessmentTemplateVersion(Base, TimestampMixin):
    __tablename__ = "assessment_template_versions"
    __table_args__ = (UniqueConstraint("template_id", "version_number", name="uq_assessment_template_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(ForeignKey("assessment_templates.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AssessmentTemplateStatus] = mapped_column(
        Enum(AssessmentTemplateStatus, name="assessment_template_status"),
        nullable=False,
        default=AssessmentTemplateStatus.DRAFT,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    total_marks: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    published_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    template: Mapped[AssessmentTemplate] = relationship(back_populates="versions")
    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        back_populates="template_version", cascade="all, delete-orphan", order_by="AssessmentQuestion.position"
    )
    published_by = relationship("User")


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    template_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_template_versions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[AssessmentQuestionType] = mapped_column(
        Enum(AssessmentQuestionType, name="assessment_question_type"), nullable=False
    )
    marks: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    template_version: Mapped[AssessmentTemplateVersion] = relationship(back_populates="questions")
    options: Mapped[list["AssessmentOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="AssessmentOption.position"
    )


class AssessmentOption(Base):
    __tablename__ = "assessment_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("assessment_questions.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped[AssessmentQuestion] = relationship(back_populates="options")


class AssessmentAssignment(Base, TimestampMixin):
    __tablename__ = "assessment_assignments"
    __table_args__ = (UniqueConstraint("application_id", "template_version_id", name="uq_application_assessment"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    template_version_id: Mapped[str] = mapped_column(ForeignKey("assessment_template_versions.id"), nullable=False)
    assigned_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AssessmentAssignmentStatus] = mapped_column(
        Enum(AssessmentAssignmentStatus, name="assessment_assignment_status"),
        nullable=False,
        default=AssessmentAssignmentStatus.ASSIGNED,
        index=True,
    )
    version_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    application = relationship("Application")
    template_version = relationship("AssessmentTemplateVersion")
    assigned_by = relationship("User")
    attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan", order_by="AssessmentAttempt.started_at"
    )


class AssessmentAttempt(Base, TimestampMixin):
    __tablename__ = "assessment_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assessment_assignments.id"), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    status: Mapped[AssessmentAttemptStatus] = mapped_column(
        Enum(AssessmentAttemptStatus, name="assessment_attempt_status"),
        nullable=False,
        default=AssessmentAttemptStatus.IN_PROGRESS,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assignment: Mapped[AssessmentAssignment] = relationship(back_populates="attempts")
    application = relationship("Application")
    responses: Mapped[list["AssessmentResponse"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")
    result: Mapped["AssessmentResult | None"] = relationship(back_populates="attempt", uselist=False)


class AssessmentResponse(Base, TimestampMixin):
    __tablename__ = "assessment_responses"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_assessment_response"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    attempt_id: Mapped[str] = mapped_column(ForeignKey("assessment_attempts.id"), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("assessment_questions.id"), nullable=False)
    selected_option_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    attempt: Mapped[AssessmentAttempt] = relationship(back_populates="responses")
    question = relationship("AssessmentQuestion")


class AssessmentResult(Base, TimestampMixin):
    __tablename__ = "assessment_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    attempt_id: Mapped[str] = mapped_column(ForeignKey("assessment_attempts.id"), nullable=False, unique=True)
    achieved_marks: Mapped[float] = mapped_column(Float, nullable=False)
    total_marks: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    question_breakdown: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    attempt: Mapped[AssessmentAttempt] = relationship(back_populates="result")
