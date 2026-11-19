import json
from pathlib import Path

import pytest
from app.core.errors import DomainError
from app.models import ScreeningRun, ScreeningRunStatus
from app.services.engine_mapping import EngineEvaluationMapper

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "engine"


def test_engine_mapper_persists_scoring_experience_and_evidence():
    payload = json.loads((FIXTURE_DIR / "candidate_evaluation_strong.json").read_text())
    run = ScreeningRun(
        application_id="application-1",
        provider="hiring-screening-engine",
        provider_engine_version="screening-v1",
        run_status=ScreeningRunStatus.RUNNING,
    )

    EngineEvaluationMapper().apply(run, payload, raw_result_ref="synthetic/evaluation.json")

    assert run.engine_contract_version == "candidate-evaluation-v1/platform-mapper-v1"
    assert run.eligibility == "PASS"
    assert run.score == 71.25
    assert run.score_before_gates == 71.25
    assert run.maximum_score == 100
    assert run.evidence_completeness == 0.78
    assert run.confirmed_experience_months == 42
    assert run.uncertain_experience_ranges[0]["label"] == "adjunct teaching"
    assert run.mandatory_requirement_results[0]["requirement_id"] == "masters-degree"
    assert run.human_review_required is True
    assert run.recommendation_label == "Human Review"
    assert len(run.criterion_results) == 2
    assert run.criterion_results[0].matched_terms == ["classroom teaching", "curriculum design", "pedagogy"]
    assert run.criterion_results[0].evidence[0].exact_text.startswith("Taught undergraduate")


def test_engine_mapper_rejects_unknown_schema_version():
    payload = json.loads((FIXTURE_DIR / "candidate_evaluation_bad_schema.json").read_text())
    run = ScreeningRun(
        application_id="application-1",
        provider="hiring-screening-engine",
        provider_engine_version="screening-v1",
        run_status=ScreeningRunStatus.RUNNING,
    )

    with pytest.raises(DomainError):
        EngineEvaluationMapper().apply(run, payload)
