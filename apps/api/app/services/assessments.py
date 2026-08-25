from __future__ import annotations

from app.core.errors import InvalidTransition, NotFound
from app.db.base import utcnow
from app.models import (
    Application,
    AssessmentAssignment,
    AssessmentAssignmentStatus,
    AssessmentAttempt,
    AssessmentAttemptStatus,
    AssessmentQuestion,
    AssessmentQuestionType,
    AssessmentResponse,
    AssessmentResult,
    AssessmentTemplateVersion,
    User,
)
from app.schemas.assessments import AssessmentSubmit
from app.services.audit import record_audit
from sqlalchemy import select
from sqlalchemy.orm import Session


def assign_configured_assessment(db: Session, application: Application, actor: User) -> AssessmentAssignment | None:
    version_id = application.job.assessment_template_version_id
    if not version_id:
        return None
    version = db.get(AssessmentTemplateVersion, version_id)
    if version is None:
        raise InvalidTransition("Configured assessment template version does not exist")
    existing = db.scalar(
        select(AssessmentAssignment)
        .where(AssessmentAssignment.application_id == application.id)
        .where(AssessmentAssignment.template_version_id == version.id)
    )
    if existing is not None:
        return existing
    assignment = AssessmentAssignment(
        application=application,
        template_version=version,
        assigned_by_id=actor.id,
        assigned_at=utcnow(),
        version_snapshot=assessment_version_snapshot(version),
    )
    db.add(assignment)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        action="assessment.auto_assign",
        entity_type="assessment_assignment",
        entity_id=assignment.id,
    )
    return assignment


def application_assessment(db: Session, application: Application) -> AssessmentAssignment | None:
    return db.scalar(
        select(AssessmentAssignment)
        .where(AssessmentAssignment.application_id == application.id)
        .order_by(AssessmentAssignment.assigned_at.desc())
        .limit(1)
    )


def start_assessment_attempt(db: Session, application: Application, assignment_id: str) -> AssessmentAttempt:
    assignment = db.get(AssessmentAssignment, assignment_id)
    if assignment is None or assignment.application_id != application.id:
        raise NotFound("Assessment assignment not found")
    active = next(
        (attempt for attempt in assignment.attempts if attempt.status == AssessmentAttemptStatus.IN_PROGRESS),
        None,
    )
    if active:
        return active
    submitted = next(
        (attempt for attempt in assignment.attempts if attempt.status == AssessmentAttemptStatus.SUBMITTED),
        None,
    )
    if submitted:
        return submitted
    attempt = AssessmentAttempt(
        assignment=assignment,
        application=application,
        started_at=utcnow(),
    )
    assignment.status = AssessmentAssignmentStatus.IN_PROGRESS
    db.add(attempt)
    db.flush()
    return attempt


def submit_assessment_attempt(
    db: Session,
    application: Application,
    attempt_id: str,
    data: AssessmentSubmit,
) -> AssessmentAttempt:
    attempt = db.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.application_id != application.id:
        raise NotFound("Assessment attempt not found")
    if attempt.status == AssessmentAttemptStatus.SUBMITTED:
        return attempt
    question_ids = {question.id for question in attempt.assignment.template_version.questions}
    for item in data.responses:
        if item.question_id not in question_ids:
            raise InvalidTransition("Assessment response does not belong to this assignment")
        response = db.scalar(
            select(AssessmentResponse)
            .where(AssessmentResponse.attempt_id == attempt.id)
            .where(AssessmentResponse.question_id == item.question_id)
        )
        if response is None:
            response = AssessmentResponse(
                attempt=attempt,
                question_id=item.question_id,
                selected_option_ids=sorted(set(item.selected_option_ids)),
                saved_at=utcnow(),
            )
            db.add(response)
        else:
            response.selected_option_ids = sorted(set(item.selected_option_ids))
            response.saved_at = utcnow()
    attempt.status = AssessmentAttemptStatus.SUBMITTED
    attempt.submitted_at = utcnow()
    attempt.assignment.status = AssessmentAssignmentStatus.SUBMITTED
    _score_attempt(db, attempt)
    return attempt


def assessment_assignment_read(assignment: AssessmentAssignment | None, *, include_result: bool) -> dict | None:
    if assignment is None:
        return None
    latest_attempt = assignment.attempts[-1] if assignment.attempts else None
    return {
        "id": assignment.id,
        "application_id": assignment.application_id,
        "status": assignment.status.value,
        "assigned_at": assignment.assigned_at,
        "title": assignment.version_snapshot.get("title", assignment.template_version.title),
        "instructions": assignment.version_snapshot.get("instructions", assignment.template_version.instructions),
        "duration_minutes": assignment.version_snapshot.get(
            "duration_minutes", assignment.template_version.duration_minutes
        ),
        "attempt": assessment_attempt_read(latest_attempt) if latest_attempt else None,
        "result": (
            assessment_result_read(latest_attempt.result)
            if include_result and latest_attempt and latest_attempt.result
            else None
        ),
    }


def assessment_attempt_read(attempt: AssessmentAttempt | None) -> dict | None:
    if attempt is None:
        return None
    return {
        "id": attempt.id,
        "assignment_id": attempt.assignment_id,
        "application_id": attempt.application_id,
        "status": attempt.status.value,
        "started_at": attempt.started_at,
        "submitted_at": attempt.submitted_at,
        "questions": [
            {
                "id": question.id,
                "position": question.position,
                "prompt": question.prompt,
                "question_type": question.question_type.value,
                "marks": question.marks,
                "options": [
                    {
                        "id": option.id,
                        "label": option.label,
                        "text": option.text,
                        "position": option.position,
                    }
                    for option in question.options
                ],
            }
            for question in attempt.assignment.template_version.questions
        ],
    }


def assessment_result_read(result: AssessmentResult | None) -> dict | None:
    if result is None:
        return None
    return {
        "achieved_marks": result.achieved_marks,
        "total_marks": result.total_marks,
        "percentage": result.percentage,
        "completed_at": result.completed_at,
        "question_breakdown": result.question_breakdown,
    }


def assessment_version_snapshot(version: AssessmentTemplateVersion) -> dict:
    return {
        "id": version.id,
        "title": version.title,
        "instructions": version.instructions,
        "duration_minutes": version.duration_minutes,
        "total_marks": version.total_marks,
        "questions": [
            {
                "id": question.id,
                "position": question.position,
                "prompt": question.prompt,
                "question_type": question.question_type.value,
                "marks": question.marks,
                "options": [
                    {
                        "id": option.id,
                        "label": option.label,
                        "text": option.text,
                        "position": option.position,
                        "is_correct": option.is_correct,
                    }
                    for option in question.options
                ],
            }
            for question in version.questions
        ],
    }


def _score_attempt(db: Session, attempt: AssessmentAttempt) -> AssessmentResult:
    responses = {response.question_id: set(response.selected_option_ids) for response in attempt.responses}
    achieved = 0.0
    total = 0.0
    breakdown = []
    for question in attempt.assignment.template_version.questions:
        total += question.marks
        selected = responses.get(question.id, set())
        correct = {option.id for option in question.options if option.is_correct}
        earned = _question_score(question, selected, correct)
        achieved += earned
        breakdown.append(
            {
                "question_id": question.id,
                "position": question.position,
                "achieved": earned,
                "marks": question.marks,
                "answered": bool(selected),
            }
        )
    result = AssessmentResult(
        attempt=attempt,
        achieved_marks=round(achieved, 2),
        total_marks=round(total, 2),
        percentage=round((achieved / total) * 100, 2) if total else 0.0,
        question_breakdown=breakdown,
        completed_at=utcnow(),
    )
    db.add(result)
    db.flush()
    return result


def _question_score(question: AssessmentQuestion, selected: set[str], correct: set[str]) -> float:
    if question.question_type == AssessmentQuestionType.SINGLE_CHOICE:
        return question.marks if selected == correct else 0.0
    if not correct:
        return 0.0
    return question.marks if selected == correct else 0.0
