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

JD_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "application/octet-stream",
}
RESUME_CONTENT_TYPES = {"application/pdf", "application/json", "application/octet-stream"}


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
        if size > self.max_upload_bytes:
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


def store_upload(db: Session, actor: User, file: UploadFile, purpose: DocumentPurpose) -> Document:
    stored = LocalDocumentStorage().save_upload(file, purpose=purpose)
    document = Document(
        purpose=purpose,
        original_filename=stored.original_filename,
        storage_key=stored.storage_key,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        uploaded_by_id=actor.id,
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
    allowed = JD_EXTENSIONS if purpose == DocumentPurpose.JOB_JD else RESUME_EXTENSIONS
    if suffix.lower() not in allowed:
        raise DomainError(f"Unsupported {purpose.value} document type: {suffix or '<none>'}")


def _validate_content_type(purpose: DocumentPurpose, content_type: str) -> None:
    allowed = JD_CONTENT_TYPES if purpose == DocumentPurpose.JOB_JD else RESUME_CONTENT_TYPES
    if content_type not in allowed:
        raise DomainError(f"Unsupported {purpose.value} content type: {content_type}")

