from datetime import datetime

from app.models import DocumentPurpose
from app.schemas.common import ApiModel


class DocumentRead(ApiModel):
    id: str
    purpose: DocumentPurpose
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    uploaded_by_id: str | None = None
    created_at: datetime
