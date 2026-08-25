from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.core.errors import DomainError, NotFound
from app.models import Document, DocumentPurpose, User
from fastapi import UploadFile
from sqlalchemy.orm import Session

JD_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
RESUME_EXTENSIONS = {".pdf", ".json"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}

JD_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "application/octet-stream",
}
RESUME_CONTENT_TYPES = {"application/pdf", "application/json", "application/octet-stream"}
PHOTO_CONTENT_TYPES = {"image/jpeg", "image/png", "application/octet-stream"}
VIDEO_CONTENT_TYPES = {"video/mp4", "video/webm", "video/quicktime", "application/octet-stream"}
PURPOSE_MAX_BYTES = {
    DocumentPurpose.RESUME: 5 * 1024 * 1024,
    DocumentPurpose.PHOTO: 2 * 1024 * 1024,
}


@dataclass(frozen=True)
class StoredDocument:
    original_filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    sha256: str


class DocumentStorage:
    def save_upload(self, file: UploadFile, *, purpose: DocumentPurpose) -> StoredDocument:
        raise NotImplementedError

    def resolve_path(self, document: Document) -> Path:
        raise NotImplementedError


class LocalDocumentStorage(DocumentStorage):
    def __init__(self, root: Path | None = None, max_upload_bytes: int | None = None):
        settings = get_settings()
        self.root = (root or Path(settings.document_storage_root)).expanduser().resolve()
        self.max_upload_bytes = max_upload_bytes or settings.max_upload_bytes

    def save_upload(self, file: UploadFile, *, purpose: DocumentPurpose) -> StoredDocument:
        filename = _safe_filename(file.filename or "")
        suffix = Path(filename).suffix.lower()
        _validate_extension(purpose, suffix)
        content_type = file.content_type or "application/octet-stream"
        _validate_content_type(purpose, content_type)

        data = file.file.read()
        size = len(data)
        if size <= 0:
            raise DomainError("Uploaded document is empty")
        max_bytes = min(PURPOSE_MAX_BYTES.get(purpose, self.max_upload_bytes), self.max_upload_bytes)
        if size > max_bytes:
            raise DomainError("Uploaded document exceeds maximum size")

        digest = sha256(data).hexdigest()
        document_id = str(uuid4())
        storage_key = f"{purpose.value}/{document_id}{suffix}"
        destination = self.root / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return StoredDocument(
            original_filename=filename,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size,
            sha256=digest,
        )

    def resolve_path(self, document: Document) -> Path:
        candidate = (self.root / document.storage_key).resolve()
        if not candidate.is_relative_to(self.root):
            raise DomainError("Stored document path escaped storage root")
        if not candidate.is_file():
            raise NotFound("Stored document payload not found")
        return candidate


def store_upload(db: Session, actor: User | None, file: UploadFile, purpose: DocumentPurpose) -> Document:
    stored = LocalDocumentStorage().save_upload(file, purpose=purpose)
    document = Document(
        purpose=purpose,
        original_filename=stored.original_filename,
        storage_key=stored.storage_key,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        uploaded_by_id=actor.id if actor else None,
    )
    db.add(document)
    db.flush()
    return document


def get_document(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFound("Document not found")
    return document


def _safe_filename(filename: str) -> str:
    if not filename.strip():
        raise DomainError("Uploaded document requires a filename")
    if "/" in filename or "\\" in filename:
        raise DomainError("Uploaded filename must not contain path separators")
    cleaned = Path(filename).name
    if cleaned in {"", ".", ".."}:
        raise DomainError("Uploaded filename is invalid")
    return cleaned


def _validate_extension(purpose: DocumentPurpose, suffix: str) -> None:
    allowed_by_purpose = {
        DocumentPurpose.JOB_JD: JD_EXTENSIONS,
        DocumentPurpose.RESUME: RESUME_EXTENSIONS,
        DocumentPurpose.PHOTO: PHOTO_EXTENSIONS,
        DocumentPurpose.INTRO_VIDEO: VIDEO_EXTENSIONS,
    }
    allowed = allowed_by_purpose[purpose]
    if suffix.lower() not in allowed:
        raise DomainError(f"Unsupported {purpose.value} document type: {suffix or '<none>'}")


def _validate_content_type(purpose: DocumentPurpose, content_type: str) -> None:
    allowed_by_purpose = {
        DocumentPurpose.JOB_JD: JD_CONTENT_TYPES,
        DocumentPurpose.RESUME: RESUME_CONTENT_TYPES,
        DocumentPurpose.PHOTO: PHOTO_CONTENT_TYPES,
        DocumentPurpose.INTRO_VIDEO: VIDEO_CONTENT_TYPES,
    }
    allowed = allowed_by_purpose[purpose]
    if content_type not in allowed:
        raise DomainError(f"Unsupported {purpose.value} content type: {content_type}")
