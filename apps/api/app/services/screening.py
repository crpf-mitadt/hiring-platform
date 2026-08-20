from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.errors import DomainError, InvalidTransition, NotFound
from app.db.base import utcnow
from app.models import (
    Application,
    ApplicationStage,
    JobRubricVersion,
    RubricVersionStatus,
    ScreeningJob,
    ScreeningJobStatus,
    ScreeningRun,
    ScreeningRunStatus,
    User,
)
from app.services.audit import record_audit
from app.services.documents import LocalDocumentStorage
from app.services.engine_mapping import EngineEvaluationMapper
from app.services.workflow import transition_application
from sqlalchemy import select
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ProviderExecutionResult:
    provider: str
    provider_engine_version: str
    payload: dict[str, Any]
    model_endpoint_slot: str | None = None
    raw_result_ref: str | None = None
    structured_jd_path: Path | None = None
    structured_resume_path: Path | None = None
    engine_code_version: str | None = None


class EngineProviderError(DomainError):
    def __init__(self, failure_code: str, message: str, *, model_endpoint_slot: str | None = None):
        self.failure_code = failure_code
        self.model_endpoint_slot = model_endpoint_slot
        super().__init__(message)


class ScreeningProvider(Protocol):
    name: str
    engine_version: str

    def evaluate(self, run: ScreeningRun) -> ProviderExecutionResult:
        ...


class MockScreeningProvider:
    name = "mock"
    engine_version = "mock-screening-v2"

    def evaluate(self, run: ScreeningRun) -> ProviderExecutionResult:
        criteria = run.rubric_version.criteria if run.rubric_version else []
        if not criteria:
            criteria = [
                {"criterion_id": "teaching", "name": "Teaching", "category": "teaching", "weight": 40},
                {"criterion_id": "skills", "name": "Skills", "category": "skill", "weight": 35},
                {"criterion_id": "experience", "name": "Experience", "category": "experience", "weight": 25},
            ]
        evaluations = []
        for index, criterion in enumerate(criteria):
            fraction = [1.0, 0.75, 0.5][index % 3]
            weight = float(criterion.get("weight", 0))
            name = criterion.get("name", criterion.get("criterion_id", f"criterion-{index + 1}"))
            evaluations.append(
                {
                    "criterion_id": criterion.get("criterion_id", f"criterion-{index + 1}"),
                    "criterion_name": name,
                    "category": criterion.get("category", "other"),
                    "weight": weight,
                    "requirement_ids": criterion.get("requirement_ids", []),
                    "match_fraction": fraction,
                    "weighted_score": round(weight * fraction, 2),
                    "status": "met" if fraction == 1.0 else "partially_met",
                    "explanation": "Synthetic deterministic provider result for workflow testing.",
                    "evidence": [
                        {
                            "source_type": "resume",
                            "source_document_id": run.resume_document_id or "synthetic-resume",
                            "page_number": 1,
                            "block_index": index,
                            "exact_text": f"Synthetic evidence for {name}.",
                            "normalized_text": f"synthetic evidence {index + 1}",
                            "evidence_status": "supported" if fraction >= 0.75 else "partially_supported",
                            "notes": "Mock provider output, not a hiring decision.",
                        }
                    ],
                    "missing_information": [] if fraction >= 0.75 else ["Additional evidence would be reviewed."],
                    "ambiguity": [],
                    "verification_needed": [],
                    "candidate_requirement": name,
                    "evidence_found": [f"Synthetic evidence for {name}."],
                    "component_assessment": {
                        "required_core_components": [name],
                        "preferred_components": criterion.get("preferred_skill_names", []),
                        "evaluation_dimension_components": criterion.get("evaluation_dimensions", []),
                        "adjacent_components_considered": criterion.get("adjacent_skill_names", []),
                        "supported_core_components": [name] if fraction >= 0.75 else [],
                        "supported_preferred_components": [],
                        "supported_evaluation_dimensions": [],
                        "supported_adjacent_components": [],
                        "missing_core_components": [] if fraction >= 0.75 else [name],
                        "missing_preferred_components": criterion.get("preferred_skill_names", []),
                        "missing_evaluation_dimensions": criterion.get("evaluation_dimensions", []),
                        "components": [],
                    },
                }
            )
        score = round(sum(item["weighted_score"] for item in evaluations), 2)
        return ProviderExecutionResult(
            provider=self.name,
            provider_engine_version=self.engine_version,
            model_endpoint_slot="mock",
            payload={
                "artifact_schema_version": "candidate-evaluation-v1",
                "evaluation_id": run.id,
                "candidate_id": run.application.candidate_id,
                "job_id": run.application.job_id,
                "scoring_version": "mock-scoring-contract-v1",
                "warnings": ["Mock provider. Do not use for real candidate decisions."],
                "mock_evaluation": True,
                "eligibility": {
                    "status": "REVIEW" if score < 85 else "PASS",
                    "checked_requirements": [],
                    "failed_requirements": [],
                    "ambiguous_requirements": [],
                    "requirement_statuses": {},
                    "requirement_details": [],
                    "explanation": "Synthetic eligibility for workflow testing.",
                },
                "criterion_evaluations": evaluations,
                "score_before_gates": score,
                "final_score": score,
                "maximum_score": 100.0,
                "evidence_completeness": 0.82,
                "evidence_completeness_diagnostics": {"mock": True},
                "experience_summary": {"confirmed_months": 36, "uncertain_ranges": []},
                "strengths": ["Meets core synthetic screening requirements"],
                "gaps": ["Some preferred evidence may need human review"],
                "missing_information": [],
                "recommendation_label": "Human Review",
                "human_review_required": True,
            },
        )


class HiringScreeningEngineProvider:
    name = "hiring-screening-engine"
    engine_version = "screening-v1"

    def evaluate(self, run: ScreeningRun) -> ProviderExecutionResult:
        if not run.rubric_version or not run.rubric_version.structured_jd_payload:
            raise EngineProviderError(
                "RUBRIC_NOT_APPROVED",
                "Real engine screening requires an approved StructuredJD rubric version",
            )
        if run.rubric_version.status != RubricVersionStatus.APPROVED:
            raise EngineProviderError("RUBRIC_NOT_APPROVED", "Screening requires the approved rubric version")
        if not run.resume_document:
            raise EngineProviderError("DOCUMENT_NOT_FOUND", "Real engine screening requires a stored resume document")

        settings = get_settings()
        engine_root = Path(settings.screening_engine_root).expanduser().resolve()
        if not engine_root.is_dir():
            raise EngineProviderError("ENGINE_CONFIGURATION_ERROR", "Screening engine root does not exist")
        output_root = Path(settings.screening_output_root).expanduser().resolve()
        run_dir = output_root / run.id
        run_dir.mkdir(parents=True, exist_ok=True)
        structured_jd_path = run_dir / "structured-jd.json"
        structured_resume_path = run_dir / "structured-resume.json"
        evaluation_path = run_dir / "evaluation.json"
        structured_jd_path.write_text(
            json.dumps(run.rubric_version.structured_jd_payload, indent=2),
            encoding="utf-8",
        )

        try:
            resume_path = LocalDocumentStorage().resolve_path(run.resume_document)
        except DomainError as error:
            raise EngineProviderError("DOCUMENT_NOT_FOUND", _safe_failure_message(error)) from error

        primary_env = _engine_environment(settings, gemma_base_url=settings.screening_gemma_base_url)
        model_endpoint_slot: str | None = None
        if resume_path.suffix.lower() == ".json":
            structured_resume_path.write_bytes(resume_path.read_bytes())
        elif resume_path.suffix.lower() == ".pdf":
            ocr_dir = run_dir / "ocr"
            _run_command(
                _engine_command(
                    settings,
                    engine_root / "scripts" / "run_full_resume_ocr.py",
                    str(resume_path),
                    "--output",
                    str(ocr_dir),
                ),
                cwd=engine_root,
                timeout=settings.screening_engine_timeout_seconds,
                env=primary_env,
                failure_code="CHANDRA_UNAVAILABLE",
            )
            model_endpoint_slot = self._structure_resume_with_gemma_fallback(
                settings=settings,
                engine_root=engine_root,
                ocr_dir=ocr_dir,
                structured_resume_path=structured_resume_path,
                candidate_id=run.application.candidate_id,
            )
        else:
            raise EngineProviderError(
                "ENGINE_CONFIGURATION_ERROR",
                "Real engine provider supports JSON or PDF resumes",
            )

        eval_env = _engine_environment(
            settings,
            gemma_base_url=(
                settings.screening_gemma_fallback_base_url
                if model_endpoint_slot == "fallback" and settings.screening_gemma_fallback_base_url
                else settings.screening_gemma_base_url
            ),
        )
        _run_command(
            _engine_command(
                settings,
                engine_root / "scripts" / "evaluate_candidate.py",
                "--candidate",
                str(structured_resume_path),
                "--jd",
                str(structured_jd_path),
                "--output",
                str(evaluation_path),
            ),
            cwd=engine_root,
            timeout=settings.screening_engine_timeout_seconds,
            env=eval_env,
            failure_code="ENGINE_EXECUTION_FAILED",
        )
        if not evaluation_path.is_file():
            raise EngineProviderError("ENGINE_OUTPUT_MISSING", "Engine evaluation artifact was not created")
        try:
            payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise EngineProviderError("ENGINE_OUTPUT_INVALID", "Engine evaluation artifact is not valid JSON") from error
        return ProviderExecutionResult(
            provider=self.name,
            provider_engine_version=self.engine_version,
            payload=payload,
            model_endpoint_slot=model_endpoint_slot,
            raw_result_ref=f"{Path(settings.screening_output_root).name}/{run.id}/evaluation.json",
            structured_jd_path=structured_jd_path,
            structured_resume_path=structured_resume_path,
            engine_code_version=_engine_git_commit(engine_root, settings),
        )

    def _structure_resume_with_gemma_fallback(
        self,
        *,
        settings,
        engine_root: Path,
        ocr_dir: Path,
        structured_resume_path: Path,
        candidate_id: str,
    ) -> str:
        slots = [("primary", settings.screening_gemma_base_url)]
        if settings.screening_gemma_fallback_base_url:
            slots.append(("fallback", settings.screening_gemma_fallback_base_url))

        last_error: EngineProviderError | None = None
        for slot, gemma_base_url in slots:
            try:
                _run_command(
                    _engine_command(
                        settings,
                        engine_root / "scripts" / "structure_resume.py",
                        str(ocr_dir),
                        "--candidate-id",
                        candidate_id,
                        "--output",
                        str(structured_resume_path),
                    ),
                    cwd=engine_root,
                    timeout=settings.screening_engine_timeout_seconds,
                    env=_engine_environment(settings, gemma_base_url=gemma_base_url),
                    failure_code="GEMMA_UNAVAILABLE",
                    model_endpoint_slot=slot,
                )
                return slot
            except EngineProviderError as error:
                last_error = error
                if error.failure_code == "GEMMA_UNAVAILABLE" and slot == "primary" and len(slots) > 1:
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise EngineProviderError("GEMMA_UNAVAILABLE", "Gemma endpoint was not configured")


def enqueue_screening_run(
    db: Session,
    *,
    application_id: str,
    actor: User,
    force: bool = False,
    retry_of_run_id: str | None = None,
) -> ScreeningRun:
    application = db.get(Application, application_id)
    if application is None:
        raise NotFound("Application not found")
    rubric_version = _current_approved_rubric(db, application)
    if rubric_version is None:
        raise InvalidTransition("Screening requires an approved rubric version")
    resume_document = application.resume_document or application.candidate.resume_document
    if resume_document is None:
        raise InvalidTransition("Screening requires a stored resume document")

    if retry_of_run_id:
        failed = db.get(ScreeningRun, retry_of_run_id)
        if failed is None or failed.run_status != ScreeningRunStatus.FAILED:
            raise InvalidTransition("Only failed screening runs can be retried")

    existing = _matching_existing_run(
        db,
        application_id=application.id,
        rubric_version_id=rubric_version.id,
        resume_sha256=resume_document.sha256,
    )
    if existing and not force and not retry_of_run_id:
        return existing

    settings = get_settings()
    provider_name = "hiring-screening-engine" if settings.screening_provider == "engine" else "mock"
    provider_version = "screening-v1" if settings.screening_provider == "engine" else "mock-screening-v2"
    run = ScreeningRun(
        application=application,
        rubric_version=rubric_version,
        retry_of_run_id=retry_of_run_id,
        jd_document_id=rubric_version.source_jd_document_id or application.job.jd_document_id,
        jd_document_sha256=rubric_version.source_jd_sha256,
        resume_document_id=resume_document.id,
        resume_document_sha256=resume_document.sha256,
        provider=provider_name,
        provider_engine_version=provider_version,
        run_status=ScreeningRunStatus.PENDING,
        attempt_count=0,
        uncertain_experience_ranges=[],
        mandatory_requirement_results=[],
        human_review_required=True,
        strengths=[],
        gaps=[],
        warnings=[],
    )
    db.add(run)
    db.flush()
    job = ScreeningJob(
        screening_run=run,
        max_attempts=settings.screening_worker_max_attempts,
        status=ScreeningJobStatus.PENDING,
    )
    db.add(job)
    db.flush()
    if application.current_stage == ApplicationStage.APPLICATION_RECEIVED:
        transition_application(
            db,
            application=application,
            actor=actor,
            new_stage=ApplicationStage.SCREENING_PENDING,
            system_transition=True,
        )
    elif application.current_stage == ApplicationStage.SCREENING_REVIEW and retry_of_run_id:
        transition_application(
            db,
            application=application,
            actor=actor,
            new_stage=ApplicationStage.SCREENING_PENDING,
            system_transition=True,
        )
    record_audit(
        db,
        actor_id=actor.id,
        action="screening.enqueue",
        entity_type="screening_run",
        entity_id=run.id,
        remarks=f"rubric={rubric_version.id} resume_sha256={resume_document.sha256}",
    )
    return run


def retry_screening_run(db: Session, *, run_id: str, actor: User) -> ScreeningRun:
    failed = db.get(ScreeningRun, run_id)
    if failed is None:
        raise NotFound("Screening run not found")
    if failed.run_status != ScreeningRunStatus.FAILED:
        raise InvalidTransition("Only failed screening runs can be retried")
    return enqueue_screening_run(
        db,
        application_id=failed.application_id,
        actor=actor,
        force=True,
        retry_of_run_id=failed.id,
    )


def process_next_screening_job(
    db: Session,
    *,
    provider: ScreeningProvider | None = None,
) -> ScreeningJob | None:
    job = db.scalar(
        select(ScreeningJob)
        .where(ScreeningJob.status == ScreeningJobStatus.PENDING)
        .order_by(ScreeningJob.created_at)
        .limit(1)
    )
    if job is None:
        return None
    return process_screening_job(db, job, provider=provider)


def process_screening_job(
    db: Session,
    job: ScreeningJob,
    *,
    provider: ScreeningProvider | None = None,
) -> ScreeningJob:
    run = job.screening_run
    actor = run.application.job.recruiter
    provider = provider or _provider_from_settings()
    job.status = ScreeningJobStatus.RUNNING
    job.locked_at = utcnow()
    job.started_at = utcnow()
    job.attempts += 1
    run.run_status = ScreeningRunStatus.RUNNING
    run.started_at = utcnow()
    run.attempt_count = job.attempts
    if run.application.current_stage == ApplicationStage.SCREENING_PENDING:
        transition_application(
            db,
            application=run.application,
            actor=actor,
            new_stage=ApplicationStage.SCREENING_RUNNING,
            system_transition=True,
        )
    db.flush()
    try:
        result = provider.evaluate(run)
        run.provider = result.provider
        run.provider_engine_version = result.provider_engine_version
        run.model_endpoint_slot = result.model_endpoint_slot
        EngineEvaluationMapper().apply(
            run,
            result.payload,
            raw_result_ref=result.raw_result_ref,
            structured_jd_path=result.structured_jd_path,
            structured_resume_path=result.structured_resume_path,
            engine_code_version=result.engine_code_version,
        )
        run.run_status = ScreeningRunStatus.COMPLETED
        run.completed_at = utcnow()
        job.status = ScreeningJobStatus.COMPLETED
        job.completed_at = utcnow()
        transition_application(
            db,
            application=run.application,
            actor=actor,
            new_stage=ApplicationStage.SCREENING_COMPLETE,
            system_transition=True,
        )
        transition_application(
            db,
            application=run.application,
            actor=actor,
            new_stage=ApplicationStage.SCREENING_REVIEW,
            system_transition=True,
        )
        record_audit(
            db,
            actor_id=actor.id,
            action="screening.complete",
            entity_type="screening_run",
            entity_id=run.id,
            remarks=f"provider={run.provider} score={run.score}",
        )
    except Exception as error:
        message = _safe_failure_message(error)
        run.run_status = ScreeningRunStatus.FAILED
        run.failed_at = utcnow()
        run.failure_code = _failure_code(error)
        run.model_endpoint_slot = getattr(error, "model_endpoint_slot", run.model_endpoint_slot)
        run.failure_message = message
        job.status = ScreeningJobStatus.FAILED
        job.failed_at = utcnow()
        job.failure_code = run.failure_code
        job.failure_message = message
        if run.application.current_stage == ApplicationStage.SCREENING_RUNNING:
            transition_application(
                db,
                application=run.application,
                actor=actor,
                new_stage=ApplicationStage.SCREENING_REVIEW,
                system_transition=True,
            )
        record_audit(
            db,
            actor_id=actor.id,
            action="screening.fail",
            entity_type="screening_run",
            entity_id=run.id,
            remarks=f"{run.failure_code}: {message}",
        )
    return job


def latest_screening_run(db: Session, application_id: str) -> ScreeningRun | None:
    return db.scalar(
        select(ScreeningRun)
        .where(ScreeningRun.application_id == application_id)
        .order_by(ScreeningRun.created_at.desc())
        .limit(1)
    )


def _provider_from_settings() -> ScreeningProvider:
    if get_settings().screening_provider == "engine":
        return HiringScreeningEngineProvider()
    return MockScreeningProvider()


def _current_approved_rubric(db: Session, application: Application) -> JobRubricVersion | None:
    rubric = application.job.rubrics[0] if application.job.rubrics else None
    if not rubric or not rubric.current_version_id:
        return None
    version = db.get(JobRubricVersion, rubric.current_version_id)
    if version is None or version.status != RubricVersionStatus.APPROVED:
        return None
    return version


def _matching_existing_run(
    db: Session,
    *,
    application_id: str,
    rubric_version_id: str,
    resume_sha256: str,
) -> ScreeningRun | None:
    return db.scalar(
        select(ScreeningRun)
        .where(ScreeningRun.application_id == application_id)
        .where(ScreeningRun.rubric_version_id == rubric_version_id)
        .where(ScreeningRun.resume_document_sha256 == resume_sha256)
        .where(ScreeningRun.run_status.in_([ScreeningRunStatus.PENDING, ScreeningRunStatus.RUNNING]))
        .order_by(ScreeningRun.created_at.desc())
        .limit(1)
    )


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
    failure_code: str,
    model_endpoint_slot: str | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise EngineProviderError(
            "ENGINE_TIMEOUT",
            "Engine command timed out",
            model_endpoint_slot=model_endpoint_slot,
        ) from error
    if completed.returncode != 0:
        diagnostic = " ".join((completed.stderr or completed.stdout).split())[:500]
        code = _classify_command_failure(failure_code, diagnostic)
        raise EngineProviderError(
            code,
            diagnostic or "Engine command failed",
            model_endpoint_slot=model_endpoint_slot,
        )
    return completed


def _engine_command(settings, script_path: Path, *args: str) -> list[str]:
    return [*shlex.split(settings.screening_engine_python), str(script_path), *args]


def _engine_environment(settings, *, gemma_base_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("CHANDRA_API_KEY", None)
    env.update(
        {
            "CHANDRA_BASE_URL": settings.screening_chandra_base_url,
            "CHANDRA_MODEL": settings.screening_chandra_model,
            "GEMMA_BASE_URL": gemma_base_url,
            "GEMMA_API_KEY": settings.screening_gemma_api_key,
            "GEMMA_MODEL": settings.screening_gemma_model,
            "GEMMA_RESUME_MAX_TOKENS": str(settings.screening_gemma_resume_max_tokens),
            "CHANDRA_OCR_RETRY_MAX_TOKENS": str(settings.screening_chandra_ocr_retry_max_tokens),
            "PIPELINE_DEBUG_RAW_RESPONSES": _bool_env(settings.screening_pipeline_debug_raw_responses),
            "LLM_REQUEST_TIMEOUT_SECONDS": str(settings.screening_engine_timeout_seconds),
        }
    )
    return env


def _bool_env(value: bool) -> str:
    return "true" if value else "false"


def _is_service_failure_code(failure_code: str) -> bool:
    return failure_code in {
        "CHANDRA_UNAVAILABLE",
        "GEMMA_UNAVAILABLE",
        "ENGINE_TIMEOUT",
        "ENGINE_OUTPUT_MISSING",
        "ENGINE_OUTPUT_INVALID",
        "ENGINE_CONFIGURATION_ERROR",
    }


def _classify_command_failure(failure_code: str, diagnostic: str) -> str:
    if failure_code in {"CHANDRA_UNAVAILABLE", "GEMMA_UNAVAILABLE"}:
        if _looks_like_transport_or_service_failure(diagnostic):
            return failure_code
        return "ENGINE_EXECUTION_FAILED"
    if _is_service_failure_code(failure_code):
        return failure_code
    return "ENGINE_EXECUTION_FAILED"


def _looks_like_transport_or_service_failure(diagnostic: str) -> bool:
    lowered = diagnostic.lower()
    markers = (
        "connection refused",
        "connection aborted",
        "connection reset",
        "connection error",
        "connecttimeout",
        "readtimeout",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "http 502",
        "http 503",
        "http 504",
        "status 502",
        "status 503",
        "status 504",
        "max retries exceeded",
        "failed to establish a new connection",
        "httpconnectionpool",
        "request failed",
        "api request failed",
    )
    return any(marker in lowered for marker in markers)


def _failure_code(error: Exception) -> str:
    if isinstance(error, EngineProviderError):
        return error.failure_code
    message = str(error)
    if "Unsupported engine evaluation artifact schema" in message:
        return "ENGINE_SCHEMA_UNSUPPORTED"
    if "document" in message.lower() and "not found" in message.lower():
        return "DOCUMENT_NOT_FOUND"
    if "rubric" in message.lower() and "approved" in message.lower():
        return "RUBRIC_NOT_APPROVED"
    return "ENGINE_EXECUTION_FAILED"


def _engine_git_commit(engine_root: Path, settings) -> str | None:
    try:
        completed = _run_command(
            [
                *shlex.split(settings.screening_engine_python),
                "-c",
                "import subprocess; "
                "print(subprocess.check_output(['git','rev-parse','--short','HEAD']).decode().strip())",
            ],
            cwd=engine_root,
            timeout=10,
            failure_code="engine_version_lookup_failed",
        )
    except Exception:
        return None
    return completed.stdout.strip()


def _safe_failure_message(error: Exception) -> str:
    return " ".join(str(error).split())[:500] or error.__class__.__name__
