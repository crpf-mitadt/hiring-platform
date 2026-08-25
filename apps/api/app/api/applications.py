from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import ActorDep, DbDep
from app.core.security import require_any_role
from app.models import ApplicationStage, HiringDecision, Role, ScreeningRun
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationTransitionRequest,
    CandidateApplicationStatus,
)
from app.schemas.screening import ScreeningDossierRead, ScreeningRunRead
from app.services.applications import (
    application_read_payload,
    candidate_safe_status,
    get_application_for_actor,
    list_applications,
    submit_application,
)
from app.services.screening import enqueue_screening_run, retry_screening_run
from app.services.workflow import transition_application

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("/jobs/{job_id}/apply", response_model=ApplicationRead)
def api_apply(db: DbDep, actor: ActorDep, job_id: str, data: ApplicationCreate):
    application = submit_application(db, actor, job_id, data)
    db.commit()
    return application_read_payload(application)


@router.get("", response_model=list[ApplicationRead])
def api_list_applications(
    db: DbDep,
    actor: ActorDep,
    job_id: str | None = None,
    stage: ApplicationStage | None = None,
):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    return [
        application_read_payload(application)
        for application in list_applications(db, actor, job_id=job_id, stage=stage)
    ]


@router.get("/mine", response_model=list[CandidateApplicationStatus])
def api_my_applications(db: DbDep, actor: ActorDep):
    applications = list_applications(db, actor)
    return [candidate_safe_status(application) for application in applications]


@router.get("/{application_id}", response_model=ApplicationRead)
def api_get_application(db: DbDep, actor: ActorDep, application_id: str):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    return application_read_payload(get_application_for_actor(db, actor, application_id))


@router.get("/{application_id}/screening", response_model=list[ScreeningRunRead])
def api_screening_runs(db: DbDep, actor: ActorDep, application_id: str):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    application = get_application_for_actor(db, actor, application_id)
    return list(
        db.scalars(
            select(ScreeningRun)
            .where(ScreeningRun.application_id == application.id)
            .order_by(ScreeningRun.created_at.desc())
        )
    )


@router.post("/{application_id}/screening-runs", response_model=ScreeningRunRead)
def api_start_screening(db: DbDep, actor: ActorDep, application_id: str):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    run = enqueue_screening_run(db, application_id=application_id, actor=actor)
    db.commit()
    return run


@router.post("/screening-runs/{run_id}/retry", response_model=ScreeningRunRead)
def api_retry_screening(db: DbDep, actor: ActorDep, run_id: str):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    run = retry_screening_run(db, run_id=run_id, actor=actor)
    db.commit()
    return run


@router.get("/{application_id}/screening-dossier", response_model=ScreeningDossierRead)
def api_screening_dossier(db: DbDep, actor: ActorDep, application_id: str):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    application = get_application_for_actor(db, actor, application_id)
    runs = list(
        db.scalars(
            select(ScreeningRun)
            .where(ScreeningRun.application_id == application.id)
            .order_by(ScreeningRun.created_at.desc())
        )
    )
    decisions = list(
        db.scalars(
            select(HiringDecision)
            .where(HiringDecision.application_id == application.id)
            .order_by(HiringDecision.timestamp.desc())
        )
    )
    return {
        "application_id": application.id,
        "current_stage": application.current_stage,
        "screening_runs": runs,
        "stage_history": application.stage_history,
        "decisions": decisions,
    }


@router.post("/{application_id}/shortlist", response_model=ApplicationRead)
def api_shortlist(
    db: DbDep, actor: ActorDep, application_id: str, data: ApplicationTransitionRequest
):
    application = get_application_for_actor(db, actor, application_id)
    transition_application(
        db,
        application=application,
        actor=actor,
        new_stage=ApplicationStage.SHORTLISTED_FOR_ASSESSMENT,
        remarks=data.remarks,
    )
    db.commit()
    return application_read_payload(application)


@router.post("/{application_id}/hold", response_model=ApplicationRead)
def api_hold(db: DbDep, actor: ActorDep, application_id: str, data: ApplicationTransitionRequest):
    application = get_application_for_actor(db, actor, application_id)
    transition_application(
        db,
        application=application,
        actor=actor,
        new_stage=ApplicationStage.SCREENING_HOLD,
        remarks=data.remarks,
    )
    db.commit()
    return application_read_payload(application)


@router.post("/{application_id}/do-not-progress", response_model=ApplicationRead)
def api_do_not_progress(
    db: DbDep, actor: ActorDep, application_id: str, data: ApplicationTransitionRequest
):
    application = get_application_for_actor(db, actor, application_id)
    transition_application(
        db,
        application=application,
        actor=actor,
        new_stage=ApplicationStage.NOT_PROGRESSED_AFTER_SCREENING,
        remarks=data.remarks,
    )
    db.commit()
    return application_read_payload(application)
