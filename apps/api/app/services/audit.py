from app.db.base import utcnow
from app.models import AuditEvent
from sqlalchemy.orm import Session


def record_audit(
    db: Session,
    *,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    remarks: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        timestamp=utcnow(),
        remarks=remarks,
    )
    db.add(event)
    return event

