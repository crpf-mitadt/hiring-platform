from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.core.errors import DomainError
from app.models import ScreeningCriterionResult, ScreeningEvidence, ScreeningRun

ENGINE_EVALUATION_CONTRACT_VERSION = "candidate-evaluation-v1/platform-mapper-v1"


class EngineEvaluationMapper:
    def apply(
        self,
        run: ScreeningRun,
        payload: dict[str, Any],
        *,
        raw_result_ref: str | None = None,
        structured_jd_path: Path | None = None,
        structured_resume_path: Path | None = None,
        engine_code_version: str | None = None,
    ) -> None:
        schema_version = payload.get("artifact_schema_version")
        if schema_version != "candidate-evaluation-v1":
            raise DomainError(f"Unsupported engine evaluation artifact schema: {schema_version}")

        run.engine_contract_version = ENGINE_EVALUATION_CONTRACT_VERSION
        run.engine_artifact_schema_version = schema_version
        run.engine_code_version = engine_code_version or payload.get("scoring_version")
        run.eligibility = (payload.get("eligibility") or {}).get("status")
        run.score = payload.get("final_score")
        run.score_before_gates = payload.get("score_before_gates")
        run.maximum_score = payload.get("maximum_score")
        run.evidence_completeness = payload.get("evidence_completeness")
        run.confirmed_experience_months = (payload.get("experience_summary") or {}).get("confirmed_months")
        run.uncertain_experience_ranges = (payload.get("experience_summary") or {}).get("uncertain_ranges", [])
        run.mandatory_requirement_results = (payload.get("eligibility") or {}).get("requirement_details", [])
        run.human_review_required = payload.get("human_review_required", True)
        run.recommendation_label = payload.get("recommendation_label")
        run.strengths = payload.get("strengths", [])
        run.gaps = payload.get("gaps", [])
        run.warnings = payload.get("warnings", [])
        run.raw_result_ref = raw_result_ref
        run.raw_result = payload
        if structured_jd_path:
            run.structured_jd_sha256 = _file_sha256(structured_jd_path)
        if structured_resume_path:
            run.structured_resume_sha256 = _file_sha256(structured_resume_path)

        run.criterion_results = [
            self._criterion_result(run, item)
            for item in payload.get("criterion_evaluations", [])
        ]

    def _criterion_result(self, run: ScreeningRun, item: dict[str, Any]) -> ScreeningCriterionResult:
        component_assessment = item.get("component_assessment") or {}
        result = ScreeningCriterionResult(
            screening_run=run,
            criterion_id=item["criterion_id"],
            criterion_name=item.get("criterion_name") or item.get("criterion_id", ""),
            category=item.get("category", ""),
            weight=item.get("weight"),
            requirement_ids=item.get("requirement_ids", []),
            status=item.get("status", "unclear"),
            match_fraction=item.get("match_fraction", 0),
            weighted_score=item.get("weighted_score", 0),
            explanation=item.get("explanation", ""),
            candidate_requirement=item.get("candidate_requirement", ""),
            evidence_found=item.get("evidence_found", []),
            missing_information=item.get("missing_information", []),
            ambiguity=item.get("ambiguity", []),
            verification_needed=item.get("verification_needed", []),
            matched_terms=_matched_terms(component_assessment),
            unmatched_terms=_unmatched_terms(component_assessment),
            raw_component_assessment=component_assessment,
        )
        result.evidence = [
            ScreeningEvidence(
                source_type=evidence.get("source_type", ""),
                source_document_id=evidence.get("source_document_id", ""),
                page_number=evidence.get("page_number"),
                block_index=evidence.get("block_index"),
                exact_text=evidence.get("exact_text", ""),
                normalized_text=evidence.get("normalized_text"),
                evidence_status=evidence.get("evidence_status", "supported"),
                notes=evidence.get("notes"),
            )
            for evidence in item.get("evidence", [])
        ]
        return result


def load_engine_artifact(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _matched_terms(component_assessment: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key in (
        "supported_core_components",
        "supported_preferred_components",
        "supported_evaluation_dimensions",
        "supported_controlled_equivalents",
        "supported_adjacent_components",
    ):
        terms.extend(str(item) for item in component_assessment.get(key, []))
    return sorted(set(terms))


def _unmatched_terms(component_assessment: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key in (
        "missing_core_components",
        "missing_preferred_components",
        "missing_evaluation_dimensions",
    ):
        terms.extend(str(item) for item in component_assessment.get(key, []))
    return sorted(set(terms))


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
