from datetime import datetime

from app.schemas.common import ApiModel


class AssessmentResponseSubmit(ApiModel):
    question_id: str
    selected_option_ids: list[str]


class AssessmentSubmit(ApiModel):
    responses: list[AssessmentResponseSubmit]


class AssessmentAttemptRead(ApiModel):
    id: str
    assignment_id: str
    application_id: str
    status: str
    started_at: datetime
    submitted_at: datetime | None
    questions: list[dict]


class AssessmentAssignmentRead(ApiModel):
    id: str
    application_id: str
    status: str
    assigned_at: datetime
    title: str
    instructions: str
    duration_minutes: int
    attempt: AssessmentAttemptRead | None = None
    result: dict | None = None
