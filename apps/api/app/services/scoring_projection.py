from __future__ import annotations

from typing import Any

from app.models import JobRoleCategory

BLOCKED_SCORING_KEYS = {
    "full_name",
    "email",
    "phone",
    "date_of_birth",
    "dob",
    "gender",
    "mother_tongue",
    "photo_document_id",
    "current_salary_lpa",
    "expected_salary_lpa",
    "languages",
    "address",
    "age",
}


def build_scoring_safe_application_projection(
    payload: dict[str, Any],
    role_category: JobRoleCategory,
) -> dict[str, Any]:
    education = payload.get("education") or {}
    experience = payload.get("experience") or {}
    research = payload.get("research") or {}
    qualifications = payload.get("qualifications") or {}
    basic = payload.get("basic") or {}

    projection: dict[str, Any] = {
        "schema_version": "application-scoring-safe-v1",
        "position": basic.get("position"),
        "designation": basic.get("designation"),
        "specialisation": basic.get("specialisation"),
        "previously_employed_with_mit_adt": basic.get("previously_employed_with_mit_adt"),
        "experience": {
            "teaching_years": experience.get("teaching_years"),
            "research_years": experience.get("research_years"),
            "industry_years": experience.get("industry_years"),
            "total_years": experience.get("total_years"),
        },
        "education": {
            "ug": education.get("ug"),
            "pg": education.get("pg"),
            "completed_pg": education.get("completed_pg"),
        },
        "qualifications": {
            "net": qualifications.get("net"),
            "set": qualifications.get("set"),
        },
    }
    if role_category == JobRoleCategory.FACULTY:
        projection["research"] = {
            "phd_status": research.get("phd_status"),
            "phd_completion_year": research.get("phd_completion_year"),
            "phd_registration_date": research.get("phd_registration_date"),
            "phd_university": research.get("phd_university"),
            "published_research_papers": research.get("published_research_papers"),
            "phd_guide": research.get("phd_guide"),
        }
    return projection


def assert_scoring_projection_is_safe(projection: dict[str, Any]) -> None:
    lowered = _flatten_keys(projection)
    blocked = sorted(key for key in BLOCKED_SCORING_KEYS if key in lowered)
    if blocked:
        raise AssertionError(f"Scoring-safe projection contains blocked keys: {', '.join(blocked)}")


def _flatten_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key).lower())
            keys.update(_flatten_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_flatten_keys(item))
    return keys
