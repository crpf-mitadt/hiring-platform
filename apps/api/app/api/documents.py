from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.api.deps import ActorDep, DbDep
from app.core.security import require_any_role
from app.models import DocumentPurpose, Role
from app.schemas.documents import DocumentRead
from app.services.documents import store_upload

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/resumes", response_model=DocumentRead)
def api_upload_resume(db: DbDep, actor: ActorDep, file: Annotated[UploadFile, File()]):
    require_any_role(actor, {Role.CANDIDATE, Role.HR_RECRUITER, Role.HIRING_ADMIN})
    document = store_upload(db, actor, file, DocumentPurpose.RESUME)
    db.commit()
    return document
