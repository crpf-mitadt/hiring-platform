from __future__ import annotations

import importlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import InvalidTransition, StructuredDomainError

REQUIREMENT_LINK_ERROR = "INVALID_SCREENING_CRITERIA"
DESIGNATION_REQUIRED = "TARGET_DESIGNATION_REQUIRED"
DESIGNATION_OPTIONS = ("Assistant Professor", "Associate Professor", "Professor")


@dataclass(frozen=True)
class StructuredJDPreflight:
    canonical_payload: dict[str, Any]
    issues: list[dict[str, Any]]


def validate_structured_jd_for_engine(
    payload: dict[str, Any],
    *,
    target_designation: str | None = None,
) -> StructuredJDPreflight:
    canonical = canonical_structured_jd_payload(payload, target_designation=target_designation)
    issues = _link_issues(canonical)
    if issues:
        raise StructuredDomainError(
            "Screening criteria need review before this batch can start.",
            code=REQUIREMENT_LINK_ERROR,
            issues=issues,
        )
    try:
        structured_jd = _structured_jd_model().model_validate(canonical)
    except Exception as error:
        raise StructuredDomainError(
            "Screening criteria need review before this batch can start.",
            code=REQUIREMENT_LINK_ERROR,
            issues=_schema_issues(error),
        ) from error
    return StructuredJDPreflight(canonical_payload=structured_jd.model_dump(mode="json"), issues=[])


def designation_options_for_structured_jd(payload: dict[str, Any]) -> list[str]:
    haystack = " ".join(
        [
            str(payload.get("job_title") or ""),
            *[
                str(requirement.get("description") or "")
                for requirement in _requirements(payload)
                if isinstance(requirement, dict)
            ],
        ]
    )
    return _mentioned_designations(haystack)


def require_target_designation_if_needed(payload: dict[str, Any], target_designation: str | None) -> None:
    options = designation_options_for_structured_jd(payload)
    if len(options) <= 1:
        return
    if target_designation not in options:
        raise StructuredDomainError(
            "Choose a target designation before confirming screening criteria.",
            code=DESIGNATION_REQUIRED,
            issues=[
                {
                    "type": "TARGET_DESIGNATION_REQUIRED",
                    "description": (
                        "This JD contains rank-specific requirements. Choose one designation for this batch."
                    ),
                    "options": options,
                }
            ],
        )


def canonical_structured_jd_payload(
    payload: dict[str, Any],
    *,
    target_designation: str | None = None,
) -> dict[str, Any]:
    canonical = {
        "schema_version": payload.get("schema_version", "structured-jd-v1"),
        "job_id": payload.get("job_id") or "bulk-jd",
        "source_document_id": payload.get("source_document_id") or "manual-jd",
        "extraction_method": payload.get("extraction_method") or "deterministic_fallback",
        "job_title": payload.get("job_title") or "Untitled role",
        "department": payload.get("department") or "",
        "role_summary": payload.get("role_summary") or "",
        "responsibilities": _string_list(payload.get("responsibilities")),
        "mandatory_requirements": _canonical_requirements(payload.get("mandatory_requirements"), target_designation),
        "preferred_requirements": _canonical_requirements(payload.get("preferred_requirements"), target_designation),
        "required_skills": _string_list(payload.get("required_skills")),
        "preferred_skills": _string_list(payload.get("preferred_skills")),
        "minimum_experience_months": payload.get("minimum_experience_months"),
        "domain": payload.get("domain") or "",
        "seniority": payload.get("seniority") or "",
        "scoring_rubric": _canonical_criteria(payload.get("scoring_rubric"), target_designation),
        "extraction_warnings": _string_list(payload.get("extraction_warnings")),
    }
    remaining_requirement_ids = {requirement["requirement_id"] for requirement in _requirements(canonical)}
    filtered_criteria = []
    for criterion in canonical["scoring_rubric"]:
        original_requirement_ids = list(criterion["requirement_ids"])
        criterion["requirement_ids"] = [
            requirement_id
            for requirement_id in criterion["requirement_ids"]
            if requirement_id in remaining_requirement_ids
        ]
        if original_requirement_ids and not criterion["requirement_ids"] and target_designation:
            continue
        filtered_criteria.append(criterion)
    canonical["scoring_rubric"] = _renormalize_criteria_weights(filtered_criteria)
    return canonical


def _canonical_requirements(value: Any, target_designation: str | None) -> list[dict[str, Any]]:
    requirements = []
    for index, entry in enumerate(value if isinstance(value, list) else [], start=1):
        if isinstance(entry, dict):
            description = str(entry.get("description") or entry.get("name") or "").strip()
            if target_designation and not _applies_to_designation(description, target_designation):
                continue
            requirements.append(
                {
                    "requirement_id": str(entry.get("requirement_id") or entry.get("id") or f"requirement-{index}"),
                    "category": _canonical_category(entry.get("category")),
                    "description": description or f"Requirement {index}",
                    "requirement_type": entry.get("requirement_type") or _requirement_type(entry),
                    "mandatory": bool(entry.get("mandatory")),
                    "preferred": bool(entry.get("preferred")),
                    "minimum_value": entry.get("minimum_value"),
                    "unit": entry.get("unit"),
                    "accepted_equivalents": _string_list(entry.get("accepted_equivalents")),
                    "evidence": entry.get("evidence") if isinstance(entry.get("evidence"), list) else [],
                    "warnings": _string_list(entry.get("warnings")),
                }
            )
        elif isinstance(entry, str) and entry.strip():
            if target_designation and not _applies_to_designation(entry, target_designation):
                continue
            requirements.append(
                {
                    "requirement_id": f"requirement-{index}",
                    "category": "other",
                    "description": entry.strip(),
                    "requirement_type": "minimum",
                    "mandatory": True,
                    "preferred": False,
                    "minimum_value": None,
                    "unit": None,
                    "accepted_equivalents": [],
                    "evidence": [],
                    "warnings": [],
                }
            )
    return requirements


def _canonical_criteria(value: Any, target_designation: str | None) -> list[dict[str, Any]]:
    criteria = []
    for index, entry in enumerate(value if isinstance(value, list) else [], start=1):
        if not isinstance(entry, dict):
            continue
        description = str(entry.get("description") or entry.get("name") or "").strip()
        if target_designation and not _applies_to_designation(description, target_designation):
            continue
        criteria.append(
            {
                "criterion_id": str(entry.get("criterion_id") or entry.get("id") or f"criterion-{index}"),
                "name": str(entry.get("name") or entry.get("criterion_id") or f"Criterion {index}"),
                "category": _canonical_category(entry.get("category")),
                "description": description or f"Screening criterion {index}",
                "weight": float(entry.get("weight") or 0),
                "mandatory": bool(entry.get("mandatory")),
                "accepted_evidence": _string_list(entry.get("accepted_evidence")),
                "scoring_guidance": str(entry.get("scoring_guidance") or ""),
                "requirement_ids": _string_list(entry.get("requirement_ids")),
                "required_skill_names": _string_list(entry.get("required_skill_names")),
                "preferred_skill_names": _string_list(entry.get("preferred_skill_names")),
                "adjacent_skill_names": _string_list(entry.get("adjacent_skill_names")),
                "evaluation_dimensions": _string_list(entry.get("evaluation_dimensions")),
            }
        )
    return criteria


def _link_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    requirements_by_id = {
        requirement["requirement_id"]: requirement
        for requirement in _requirements(payload)
        if isinstance(requirement, dict) and requirement.get("requirement_id")
    }
    issues = []
    mandatory_linked_to_mandatory: set[str] = set()
    for criterion in payload.get("scoring_rubric", []):
        if not isinstance(criterion, dict):
            continue
        for requirement_id in _string_list(criterion.get("requirement_ids")):
            requirement = requirements_by_id.get(requirement_id)
            if requirement is None:
                issues.append(
                    {
                        "type": "UNKNOWN_REQUIREMENT_ID",
                        "requirement_id": requirement_id,
                        "criterion_id": criterion.get("criterion_id"),
                        "description": "Criterion references a requirement ID that does not exist in the JD.",
                    }
                )
                continue
            if requirement.get("mandatory") and criterion.get("mandatory"):
                mandatory_linked_to_mandatory.add(requirement_id)
            if requirement.get("mandatory") and not criterion.get("mandatory"):
                issues.append(
                    {
                        "type": "MANDATORY_LINK_CONFLICT",
                        "requirement_id": requirement_id,
                        "criterion_id": criterion.get("criterion_id"),
                        "description": "Mandatory requirement is linked only to a non-mandatory criterion.",
                    }
                )
            if requirement.get("preferred") and criterion.get("mandatory"):
                issues.append(
                    {
                        "type": "PREFERRED_MARKED_MANDATORY",
                        "requirement_id": requirement_id,
                        "criterion_id": criterion.get("criterion_id"),
                        "description": "Preferred requirement is linked to a mandatory screening criterion.",
                    }
                )
    for requirement_id, requirement in requirements_by_id.items():
        if requirement.get("mandatory") and requirement_id not in mandatory_linked_to_mandatory:
            issues.append(
                {
                    "type": "UNLINKED_MANDATORY_REQUIREMENT",
                    "requirement_id": requirement_id,
                    "description": "Mandatory requirement is not linked to any mandatory screening criterion.",
                }
            )
    return issues


def _schema_issues(error: Exception) -> list[dict[str, Any]]:
    if hasattr(error, "errors"):
        return [
            {
                "type": "STRUCTURED_JD_SCHEMA_ERROR",
                "field": ".".join(str(part) for part in issue.get("loc", [])),
                "description": str(issue.get("msg") or "StructuredJD validation failed."),
            }
            for issue in error.errors()
        ]
    return [{"type": "STRUCTURED_JD_SCHEMA_ERROR", "description": "StructuredJD validation failed."}]


def _renormalize_criteria_weights(criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(float(criterion.get("weight") or 0) for criterion in criteria)
    if not criteria or round(total, 3) == 100 or total <= 0:
        return criteria
    adjusted = []
    running = 0.0
    for criterion in criteria[:-1]:
        next_criterion = dict(criterion)
        next_criterion["weight"] = round(float(criterion["weight"]) * 100 / total, 3)
        running += next_criterion["weight"]
        adjusted.append(next_criterion)
    last = dict(criteria[-1])
    last["weight"] = round(100 - running, 3)
    adjusted.append(last)
    return adjusted


def _structured_jd_model():
    try:
        return importlib.import_module("chandra_eval.schemas.jd").StructuredJD
    except ModuleNotFoundError:
        settings = get_settings()
        engine_src = Path(settings.screening_engine_root).expanduser().resolve() / "src"
        if not engine_src.is_dir():
            raise InvalidTransition("Screening engine StructuredJD schema is unavailable") from None
        sys.path.insert(0, str(engine_src))
        return importlib.import_module("chandra_eval.schemas.jd").StructuredJD


def _requirements(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *[entry for entry in payload.get("mandatory_requirements", []) if isinstance(entry, dict)],
        *[entry for entry in payload.get("preferred_requirements", []) if isinstance(entry, dict)],
    ]


def _canonical_category(value: Any) -> str:
    category = str(value or "other").strip().lower()
    if category == "eligibility":
        return "certification"
    allowed = {
        "education",
        "experience",
        "skill",
        "certification",
        "domain",
        "responsibility",
        "research",
        "teaching",
        "leadership",
        "project",
        "language",
        "other",
    }
    return category if category in allowed else category


def _requirement_type(entry: dict[str, Any]) -> str:
    if entry.get("mandatory"):
        return "minimum"
    if entry.get("preferred"):
        return "preferred"
    return "informational"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(entry).strip() for entry in value if str(entry).strip()]


def _applies_to_designation(text: str, target_designation: str) -> bool:
    if not text:
        return True
    mentioned = _mentioned_designations(text)
    return not mentioned or target_designation in mentioned


def _mentioned_designations(text: str) -> list[str]:
    if not text:
        return []
    mentioned = []
    if re.search(r"\bAssistant\s+Professor\b", text, re.I):
        mentioned.append("Assistant Professor")
    if re.search(r"\bAssociate\s+Professor\b", text, re.I):
        mentioned.append("Associate Professor")
    text_without_qualified_professor = re.sub(r"\b(?:Assistant|Associate)\s+Professor\b", "", text, flags=re.I)
    if re.search(r"\bProfessor\b", text_without_qualified_professor, re.I):
        mentioned.append("Professor")
    return mentioned
