from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Job, JobRubricVersion, User
from app.schemas.jobs import RubricVersionCreate
from app.services.documents import LocalDocumentStorage
from app.services.jobs import add_rubric_version
from app.services.screening import _engine_command, _engine_environment
from sqlalchemy.orm import Session

RUBRIC_PROVIDER_CONTRACT_VERSION = "platform-rubric-provider-v1"


@dataclass(frozen=True)
class RubricProviderResult:
    provider: str
    structured_jd: dict
    engine_mapping: dict


class RubricProvider(Protocol):
    name: str

    def generate(self, job: Job) -> RubricProviderResult:
        ...


class MockRubricProvider:
    name = "mock-rubric"

    def generate(self, job: Job) -> RubricProviderResult:
        criteria = [
            {
                "criterion_id": "core-teaching",
                "name": "Core teaching capability",
                "category": "teaching",
                "description": "Evidence of teaching or instructional delivery.",
                "weight": 35,
                "mandatory": True,
                "required_skill_names": ["Teaching"],
                "preferred_skill_names": [],
                "adjacent_skill_names": ["Mentoring"],
                "evaluation_dimensions": ["student-facing delivery"],
            },
            {
                "criterion_id": "technical-depth",
                "name": "Technical depth",
                "category": "skill",
                "description": "Evidence of role-relevant technical knowledge.",
                "weight": 40,
                "mandatory": True,
                "required_skill_names": ["Python"],
                "preferred_skill_names": ["Research"],
                "adjacent_skill_names": ["Data analysis"],
                "evaluation_dimensions": ["core skill evidence"],
            },
            {
                "criterion_id": "experience",
                "name": "Confirmed experience",
                "category": "experience",
                "description": "Confirmed relevant work or academic experience.",
                "weight": 25,
                "mandatory": False,
                "required_skill_names": [],
                "preferred_skill_names": [],
                "adjacent_skill_names": [],
                "evaluation_dimensions": ["confirmed months"],
            },
        ]
        structured = {
            "schema_version": "structured-jd-v1",
            "job_id": job.id,
            "source_document_id": job.jd_document.id if job.jd_document else job.jd_document_ref or "manual-jd",
            "extraction_method": "mock_gemma",
            "job_title": job.title,
            "department": job.department.name if job.department else "",
            "role_summary": job.description,
            "responsibilities": [],
            "mandatory_requirements": [],
            "preferred_requirements": [],
            "required_skills": ["Teaching", "Python"],
            "preferred_skills": ["Research"],
            "minimum_experience_months": 24,
            "domain": job.department.name if job.department else "",
            "seniority": "",
            "scoring_rubric": criteria,
            "extraction_warnings": ["Mock rubric provider output for local review."],
        }
        return RubricProviderResult(
            provider=self.name,
            structured_jd=structured,
            engine_mapping={
                "contract_version": RUBRIC_PROVIDER_CONTRACT_VERSION,
                "source": self.name,
                "engine_schema": "StructuredJD",
            },
        )


class HiringScreeningEngineRubricProvider:
    name = "hiring-screening-engine-rubric"

    def generate(self, job: Job) -> RubricProviderResult:
        if not job.jd_document:
            raise DomainError("Engine rubric generation requires an uploaded JD document")
        settings = get_settings()
        engine_root = Path(settings.screening_engine_root).expanduser().resolve()
        output_root = Path(settings.screening_output_root).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"structured-jd-{job.id}.json"
        jd_path = LocalDocumentStorage().resolve_path(job.jd_document)
        command = _engine_command(
            settings,
            engine_root / "scripts" / "extract_jd.py",
            str(jd_path),
            "--job-id",
            job.id,
            "--output",
            str(output_path),
        )
        completed = subprocess.run(
            command,
            cwd=engine_root,
            env=_engine_environment(settings, gemma_base_url=settings.screening_gemma_base_url),
            text=True,
            capture_output=True,
            timeout=settings.screening_engine_timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise DomainError(_safe_subprocess_error("rubric_generation_failed", completed.stderr))
        structured = json.loads(output_path.read_text(encoding="utf-8"))
        return RubricProviderResult(
            provider=self.name,
            structured_jd=structured,
            engine_mapping={
                "contract_version": RUBRIC_PROVIDER_CONTRACT_VERSION,
                "source": self.name,
                "engine_schema": "StructuredJD",
            },
        )


def generate_rubric_version(db: Session, actor: User, job: Job, *, provider: RubricProvider) -> JobRubricVersion:
    result = provider.generate(job)
    criteria = result.structured_jd.get("scoring_rubric", [])
    return add_rubric_version(
        db,
        actor,
        job.id,
        RubricVersionCreate(
            criteria=criteria,
            proposed_by=result.provider,
            engine_mapping=result.engine_mapping,
            structured_jd_payload=result.structured_jd,
            source_jd_document_id=job.jd_document_id,
        ),
    )


def _safe_subprocess_error(code: str, stderr: str) -> str:
    excerpt = " ".join((stderr or "").split())[:500]
    return f"{code}: {excerpt or 'engine command failed'}"
