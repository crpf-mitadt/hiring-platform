from dataclasses import dataclass
from typing import Protocol

from app.core.errors import NotFound
from app.db.base import utcnow
from app.models import (
    Application,
    ApplicationStage,
    JobRubric,
    JobRubricVersion,
    ScreeningCriterionResult,
    ScreeningEvidence,
    ScreeningRun,
    ScreeningRunStatus,
    User,
)
from app.services.workflow import transition_application
from sqlalchemy import select
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ScreeningProviderResult:
    provider: str
    provider_engine_version: str
    eligibility: str
    score: float
    evidence_completeness: float
    confirmed_experience_months: int
    strengths: list[str]
    gaps: list[str]
    warnings: list[str]
    raw_result: dict
    criteria: list[dict]


class ScreeningProvider(Protocol):
    name: str
    engine_version: str

    def evaluate(self, application: Application, rubric_version: JobRubricVersion | None) -> ScreeningProviderResult:
        ...


class MockScreeningProvider:
    name = "mock"
    engine_version = "mock-screening-v1"

    def evaluate(
        self, application: Application, rubric_version: JobRubricVersion | None
    ) -> ScreeningProviderResult:
        criteria = rubric_version.criteria if rubric_version else []
        if not criteria:
            criteria = [
                {
                    "criterion_id": "required-education",
                    "name": "Relevant academic background",
                    "category": "education",
                    "weight": 40,
                },
                {
                    "criterion_id": "required-experience",
                    "name": "Confirmed relevant experience",
                    "category": "experience",
                    "weight": 35,
                },
                {
                    "criterion_id": "preferred-skills",
                    "name": "Preferred role skills",
                    "category": "skill",
                    "weight": 25,
                },
            ]
        produced = []
        for index, criterion in enumerate(criteria):
            fraction = [1.0, 0.75, 0.5][index % 3]
            weight = float(criterion.get("weight", 0))
            produced.append(
                {
                    "criterion_id": criterion.get("criterion_id", f"criterion-{index + 1}"),
                    "criterion_name": criterion.get("name", "Screening criterion"),
                    "category": criterion.get("category", "other"),
                    "status": "met" if fraction == 1.0 else "partially_met",
                    "match_fraction": fraction,
                    "weighted_score": round(weight * fraction, 2),
                    "explanation": "Synthetic deterministic provider result for workflow testing.",
                    "missing_information": [] if fraction >= 0.75 else ["Additional evidence would be reviewed."],
                    "raw_component_assessment": {
                        "mock": True,
                        "required_core_components": [criterion.get("name", "criterion")],
                    },
                    "evidence": [
                        {
                            "source_type": "resume",
                            "source_document_id": application.resume_document_ref or "synthetic-resume-ref",
                            "page_number": 1,
                            "block_index": index,
                            "exact_text": f"Synthetic evidence for {criterion.get('name', 'criterion')}.",
                            "normalized_text": f"synthetic evidence {index + 1}",
                            "evidence_status": "supported" if fraction >= 0.75 else "partially_supported",
                            "notes": "Mock provider output, not a hiring decision.",
                        }
                    ],
                }
            )
        score = round(sum(item["weighted_score"] for item in produced), 2)
        return ScreeningProviderResult(
            provider=self.name,
            provider_engine_version=self.engine_version,
            eligibility="REVIEW" if score < 85 else "PASS",
            score=score,
            evidence_completeness=0.82,
            confirmed_experience_months=36,
            strengths=["Meets core synthetic screening requirements"],
            gaps=["Some preferred evidence may need human review"],
            warnings=["Mock provider. Do not use for real candidate decisions."],
            raw_result={
                "artifact_schema_version": "candidate-evaluation-v1",
                "mock_evaluation": True,
                "human_review_required": True,
            },
            criteria=produced,
        )


class BackgroundJobRunner(Protocol):
    def enqueue_screening(self, db: Session, *, application_id: str, actor_id: str) -> ScreeningRun:
        ...


class InProcessScreeningRunner:
    def __init__(self, provider: ScreeningProvider | None = None):
        self.provider = provider or MockScreeningProvider()

    def enqueue_screening(self, db: Session, *, application_id: str, actor_id: str) -> ScreeningRun:
        actor = db.get(User, actor_id)
        application = db.get(Application, application_id)
        if actor is None or application is None:
            raise NotFound("Actor or application not found")
        if application.current_stage == ApplicationStage.SCREENING_PENDING:
            transition_application(
                db,
                application=application,
                actor=actor,
                new_stage=ApplicationStage.SCREENING_RUNNING,
                system_transition=True,
            )
        rubric_version = _current_approved_rubric(db, application)
        run = ScreeningRun(
            application=application,
            rubric_version=rubric_version,
            provider=self.provider.name,
            provider_engine_version=self.provider.engine_version,
            run_status=ScreeningRunStatus.RUNNING,
            started_at=utcnow(),
        )
        db.add(run)
        db.flush()
        result = self.provider.evaluate(application, rubric_version)
        run.run_status = ScreeningRunStatus.COMPLETE
        run.completed_at = utcnow()
        run.eligibility = result.eligibility
        run.score = result.score
        run.evidence_completeness = result.evidence_completeness
        run.confirmed_experience_months = result.confirmed_experience_months
        run.strengths = result.strengths
        run.gaps = result.gaps
        run.warnings = result.warnings
        run.raw_result = result.raw_result
        for criterion in result.criteria:
            evidence_items = criterion.pop("evidence", [])
            row = ScreeningCriterionResult(screening_run=run, **criterion)
            row.evidence = [ScreeningEvidence(**item) for item in evidence_items]
            db.add(row)
        transition_application(
            db,
            application=application,
            actor=actor,
            new_stage=ApplicationStage.SCREENING_COMPLETE,
            system_transition=True,
        )
        transition_application(
            db,
            application=application,
            actor=actor,
            new_stage=ApplicationStage.SCREENING_REVIEW,
            system_transition=True,
        )
        return run


def _current_approved_rubric(db: Session, application: Application) -> JobRubricVersion | None:
    stmt = (
        select(JobRubricVersion)
        .where(JobRubricVersion.status == "approved")
        .join(JobRubricVersion.rubric)
        .where(JobRubric.job_id == application.job_id)
        .order_by(JobRubricVersion.version_number.desc())
    )
    return db.scalar(stmt)
