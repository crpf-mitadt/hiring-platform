from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import ActorDep, DbDep
from app.core.security import require_any_role
from app.models import Application, ApplicationStage, Job, JobStatus, Role

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/recruitment")
def recruitment_dashboard(db: DbDep, actor: ActorDep) -> dict:
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    return {
        "open_jobs": db.scalar(select(func.count()).select_from(Job).where(Job.status == JobStatus.PUBLISHED)),
        "applications_received": db.scalar(select(func.count()).select_from(Application)),
        "screening_reviews_pending": db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.current_stage == ApplicationStage.SCREENING_REVIEW)
        ),
        "shortlisted_for_assessment": db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.current_stage == ApplicationStage.SHORTLISTED_FOR_ASSESSMENT)
        ),
    }
