from typing import Annotated

from app.core.errors import InvalidTransition
from app.db.base import utcnow
from app.models import (
    Application,
    ApplicationIntroVideo,
    DocumentPurpose,
    InterviewSchedule,
    InterviewStatus,
    IntroVideoMode,
    IntroVideoStatus,
)
from app.services.documents import store_upload
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session


def ensure_followup_records(db: Session, application: Application) -> None:
    if application.job.intro_video_mode != IntroVideoMode.NONE and intro_video_for_application(db, application) is None:
        db.add(ApplicationIntroVideo(application=application, status=IntroVideoStatus.NOT_UPLOADED))
    if interview_for_application(db, application) is None:
        db.add(InterviewSchedule(application=application, status=InterviewStatus.NOT_SCHEDULED))
    db.flush()


def intro_video_for_application(db: Session, application: Application) -> ApplicationIntroVideo | None:
    return db.scalar(select(ApplicationIntroVideo).where(ApplicationIntroVideo.application_id == application.id))


def interview_for_application(db: Session, application: Application) -> InterviewSchedule | None:
    return db.scalar(select(InterviewSchedule).where(InterviewSchedule.application_id == application.id))


def upload_intro_video(
    db: Session,
    application: Application,
    file: Annotated[UploadFile, "intro-video"],
) -> ApplicationIntroVideo:
    if application.job.intro_video_mode == IntroVideoMode.NONE:
        raise InvalidTransition("Intro video is not configured for this job")
    record = intro_video_for_application(db, application)
    if record is None:
        record = ApplicationIntroVideo(application=application)
        db.add(record)
        db.flush()
    document = store_upload(db, None, file, DocumentPurpose.INTRO_VIDEO)
    record.document_id = document.id
    record.storage_ref = document.storage_key
    record.status = IntroVideoStatus.UPLOADED
    record.uploaded_at = utcnow()
    record.skipped_at = None
    db.flush()
    return record


def skip_intro_video(db: Session, application: Application) -> ApplicationIntroVideo:
    if application.job.intro_video_mode == IntroVideoMode.REQUIRED:
        raise InvalidTransition("Intro video is required for this job")
    record = intro_video_for_application(db, application)
    if record is None:
        record = ApplicationIntroVideo(application=application)
        db.add(record)
    record.status = IntroVideoStatus.SKIPPED
    record.skipped_at = utcnow()
    db.flush()
    return record


def intro_video_read(record: ApplicationIntroVideo | None) -> dict | None:
    if record is None:
        return None
    return {
        "id": record.id,
        "status": record.status.value,
        "document_id": record.document_id,
        "uploaded_at": record.uploaded_at,
        "skipped_at": record.skipped_at,
    }


def interview_read(record: InterviewSchedule | None) -> dict | None:
    if record is None:
        return None
    return {
        "id": record.id,
        "status": record.status.value,
        "scheduled_at": record.scheduled_at,
        "timezone": record.timezone,
        "candidate_instructions": record.candidate_instructions,
    }
