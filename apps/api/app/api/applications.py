from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile
from sqlalchemy import select

from app.api.deps import ActorDep, ApplicationAccessDep, DbDep
from app.core.config import get_settings
from app.core.security import require_any_role
from app.models import ApplicationStage, HiringDecision, Role, ScreeningRun
from app.schemas.applications import (
    ApplicationAccessExchangeRequest,
    ApplicationCreate,
    ApplicationRead,
    ApplicationTransitionRequest,
    CandidateApplicationStatus,
    PublicApplicationCreate,
    PublicApplicationSubmitRead,
)
from app.schemas.assessments import AssessmentAssignmentRead, AssessmentAttemptRead, AssessmentSubmit
from app.schemas.screening import ScreeningDossierRead, ScreeningRunRead
from app.services.application_access import exchange_application_access_token
from app.services.applications import (
    application_read_payload,
    candidate_safe_status,
    get_application_for_actor,
    list_applications,
    load_application_followup_reads,
    submit_application,
    submit_public_application,
)
from app.services.assessments import (
    application_assessment,
    assessment_assignment_read,
    assessment_attempt_read,
    start_assessment_attempt,
    submit_assessment_attempt,
)
from app.services.followup import (
    interview_for_application,
    interview_read,
    intro_video_for_application,
    intro_video_read,
    skip_intro_video,
    upload_intro_video,
)
from app.services.screening import enqueue_screening_run, retry_screening_run
from app.services.workflow import transition_application

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("/jobs/{job_id}/apply", response_model=ApplicationRead)
def api_apply(db: DbDep, actor: ActorDep, job_id: str, data: ApplicationCreate):
    application = submit_application(db, actor, job_id, data)
    db.commit()
    return application_read_payload(application)


@router.post("/public/jobs/{job_id}/apply", response_model=PublicApplicationSubmitRead)
def api_public_apply(db: DbDep, job_id: str, data: PublicApplicationCreate):
    application, continuation = submit_public_application(db, job_id, data)
    db.commit()
    return {
        "id": application.id,
        "job_id": application.job_id,
        "job_title": application.job.title,
        "submitted_at": application.submitted_at,
        "status_label": "Application received",
        "continuation_url": continuation,
    }


@router.post("/application-access/exchange")
def api_exchange_application_access(db: DbDep, response: Response, data: ApplicationAccessExchangeRequest):
    _, session_token = exchange_application_access_token(db, data.token)
    settings = get_settings()
    response.set_cookie(
        settings.application_access_cookie_name,
        session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.application_access_session_ttl_hours * 3600,
    )
    db.commit()
    return {"ok": True}


@router.get("/application-access/application", response_model=CandidateApplicationStatus)
def api_application_access_status(db: DbDep, application: ApplicationAccessDep):
    load_application_followup_reads(db, application)
    return candidate_safe_status(application)


@router.get("/application-access/assessment", response_model=AssessmentAssignmentRead | None)
def api_application_access_assessment(db: DbDep, application: ApplicationAccessDep):
    assignment = application_assessment(db, application)
    return assessment_assignment_read(assignment, include_result=False)


@router.post("/application-access/assessments/{assignment_id}/start", response_model=AssessmentAttemptRead)
def api_application_access_start_assessment(db: DbDep, assignment_id: str, application: ApplicationAccessDep):
    attempt = start_assessment_attempt(db, application, assignment_id)
    db.commit()
    return assessment_attempt_read(attempt)


@router.post("/application-access/assessments/attempts/{attempt_id}/submit", response_model=AssessmentAttemptRead)
def api_application_access_submit_assessment(
    db: DbDep,
    attempt_id: str,
    data: AssessmentSubmit,
    application: ApplicationAccessDep,
):
    attempt = submit_assessment_attempt(db, application, attempt_id, data)
    db.commit()
    return assessment_attempt_read(attempt)


@router.post("/application-access/intro-video", response_model=dict)
def api_application_access_upload_intro_video(
    db: DbDep,
    file: Annotated[UploadFile, File()],
    application: ApplicationAccessDep,
):
    record = upload_intro_video(db, application, file)
    db.commit()
    return intro_video_read(record)


@router.post("/application-access/intro-video/skip", response_model=dict)
def api_application_access_skip_intro_video(db: DbDep, application: ApplicationAccessDep):
    record = skip_intro_video(db, application)
    db.commit()
    return intro_video_read(record)


@router.get("", response_model=list[ApplicationRead])
def api_list_applications(
    db: DbDep,
    actor: ActorDep,
    job_id: str | None = None,
    stage: ApplicationStage | None = None,
):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    results = list_applications(db, actor, job_id=job_id, stage=stage)
    for application in results:
        load_application_followup_reads(db, application)
    return [application_read_payload(application) for application in results]


@router.get("/mine", response_model=list[CandidateApplicationStatus])
def api_my_applications(db: DbDep, actor: ActorDep):
    applications = list_applications(db, actor)
    return [candidate_safe_status(application) for application in applications]


@router.get("/{application_id}", response_model=ApplicationRead)
def api_get_application(db: DbDep, actor: ActorDep, application_id: str):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    application = get_application_for_actor(db, actor, application_id)
    load_application_followup_reads(db, application)
    return application_read_payload(application)


@router.get("/{application_id}/screening", response_model=list[ScreeningRunRead])
def api_screening_runs(db: DbDep, actor: ActorDep, application_id: str):
    require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    application = get_application_for_actor(db, actor, application_id)
    load_application_followup_reads(db, application)
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
        "application": application_read_payload(application),
        "assessment": assessment_assignment_read(application_assessment(db, application), include_result=True),
        "intro_video": intro_video_read(intro_video_for_application(db, application)),
        "interview": interview_read(interview_for_application(db, application)),
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
