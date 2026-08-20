from fastapi import APIRouter

from app.api.deps import ActorDep, DbDep
from app.core.security import require_any_role
from app.models import Role
from app.schemas.screening import ScreeningJobRead
from app.services.screening import process_next_screening_job

router = APIRouter(prefix="/screening-jobs", tags=["screening-jobs"])


@router.post("/run-next", response_model=ScreeningJobRead | None)
def api_run_next_screening_job(db: DbDep, actor: ActorDep):
    require_any_role(actor, {Role.HR_RECRUITER, Role.HIRING_ADMIN})
    job = process_next_screening_job(db)
    db.commit()
    return job
