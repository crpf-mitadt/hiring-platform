from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AuditEventRead(ApiModel):
    id: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    timestamp: datetime
    remarks: str | None

