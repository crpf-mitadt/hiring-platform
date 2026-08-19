from app.core.errors import InvalidTransition, NotFound
from app.core.security import require_any_role
from app.db.base import utcnow
from app.models import (
    Application,
    ApplicationStage,
    ApplicationStageHistory,
    HiringDecision,
    HiringDecisionType,
    Role,
    User,
)
from app.services.audit import record_audit
from sqlalchemy.orm import Session

LEGAL_TRANSITIONS: dict[ApplicationStage, set[ApplicationStage]] = {
    ApplicationStage.APPLICATION_RECEIVED: {ApplicationStage.SCREENING_PENDING},
    ApplicationStage.SCREENING_PENDING: {ApplicationStage.SCREENING_RUNNING},
    ApplicationStage.SCREENING_RUNNING: {ApplicationStage.SCREENING_COMPLETE},
    ApplicationStage.SCREENING_COMPLETE: {ApplicationStage.SCREENING_REVIEW},
    ApplicationStage.SCREENING_REVIEW: {
        ApplicationStage.SHORTLISTED_FOR_ASSESSMENT,
        ApplicationStage.SCREENING_HOLD,
        ApplicationStage.NOT_PROGRESSED_AFTER_SCREENING,
    },
    ApplicationStage.SCREENING_HOLD: {
        ApplicationStage.SCREENING_REVIEW,
        ApplicationStage.SHORTLISTED_FOR_ASSESSMENT,
        ApplicationStage.NOT_PROGRESSED_AFTER_SCREENING,
    },
    ApplicationStage.SHORTLISTED_FOR_ASSESSMENT: set(),
    ApplicationStage.NOT_PROGRESSED_AFTER_SCREENING: set(),
}

HUMAN_CONSEQUENTIAL_STAGES = {
    ApplicationStage.SHORTLISTED_FOR_ASSESSMENT,
    ApplicationStage.SCREENING_HOLD,
    ApplicationStage.NOT_PROGRESSED_AFTER_SCREENING,
}

HUMAN_DECISION_BY_STAGE = {
    ApplicationStage.SHORTLISTED_FOR_ASSESSMENT: HiringDecisionType.ANOTHER_ROUND,
    ApplicationStage.SCREENING_HOLD: HiringDecisionType.HOLD,
    ApplicationStage.NOT_PROGRESSED_AFTER_SCREENING: HiringDecisionType.NOT_SELECTED,
}


def get_application(db: Session, application_id: str) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise NotFound("Application not found")
    return application


def transition_application(
    db: Session,
    *,
    application: Application,
    actor: User,
    new_stage: ApplicationStage,
    remarks: str | None = None,
    system_transition: bool = False,
) -> ApplicationStageHistory | None:
    allowed = LEGAL_TRANSITIONS[application.current_stage]
    if new_stage not in allowed:
        raise InvalidTransition(f"Cannot move from {application.current_stage.value} to {new_stage.value}")
    if not system_transition:
        require_any_role(actor, {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN})
    if new_stage in HUMAN_CONSEQUENTIAL_STAGES and not (remarks and remarks.strip()):
        raise InvalidTransition("Remarks are mandatory for this human screening decision")

    previous = application.current_stage
    application.current_stage = new_stage
    history: ApplicationStageHistory | None = None
    if not system_transition or new_stage in HUMAN_CONSEQUENTIAL_STAGES:
        history = ApplicationStageHistory(
            application=application,
            previous_stage=previous,
            new_stage=new_stage,
            actor_id=actor.id,
            timestamp=utcnow(),
            remarks=remarks,
        )
        db.add(history)
    if new_stage in HUMAN_CONSEQUENTIAL_STAGES:
        db.add(
            HiringDecision(
                application=application,
                decision=HUMAN_DECISION_BY_STAGE[new_stage],
                actor_id=actor.id,
                timestamp=utcnow(),
                remarks=remarks or "",
            )
        )
    record_audit(
        db,
        actor_id=actor.id,
        action=f"application.transition.{new_stage.value.lower()}",
        entity_type="application",
        entity_id=application.id,
        remarks=remarks,
    )
    return history

