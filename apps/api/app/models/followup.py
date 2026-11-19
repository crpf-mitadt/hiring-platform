import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class IntroVideoStatus(str, enum.Enum):
    NOT_UPLOADED = "NOT_UPLOADED"
    UPLOADED = "UPLOADED"
    SKIPPED = "SKIPPED"


class InterviewStatus(str, enum.Enum):
    NOT_SCHEDULED = "NOT_SCHEDULED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ApplicationIntroVideo(Base, TimestampMixin):
    __tablename__ = "application_intro_videos"
    __table_args__ = (UniqueConstraint("application_id", name="uq_application_intro_video"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    status: Mapped[IntroVideoStatus] = mapped_column(
        Enum(IntroVideoStatus, name="application_intro_video_status"),
        nullable=False,
        default=IntroVideoStatus.NOT_UPLOADED,
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    storage_ref: Mapped[str | None] = mapped_column(String(500))

    application = relationship("Application")
    document = relationship("Document")


class InterviewSchedule(Base, TimestampMixin):
    __tablename__ = "interview_schedules"
    __table_args__ = (UniqueConstraint("application_id", name="uq_application_interview_schedule"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, name="candidate_interview_status"),
        nullable=False,
        default=InterviewStatus.NOT_SCHEDULED,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str | None] = mapped_column(String(80))
    candidate_instructions: Mapped[str | None] = mapped_column(Text)
    scheduled_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    application = relationship("Application")
    scheduled_by = relationship("User")
