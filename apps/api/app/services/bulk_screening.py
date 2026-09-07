from __future__ import annotations

import json
import logging
import mimetypes
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.errors import DomainError, InvalidTransition, NotFound, StructuredDomainError
from app.core.security import require_any_role
from app.db.base import utcnow
from app.models import (
    BulkScreeningBatch,
    BulkScreeningBatchStatus,
    BulkScreeningClassification,
    BulkScreeningCriterionResult,
    BulkScreeningEvidence,
    BulkScreeningItem,
    BulkScreeningItemStatus,
    BulkScreeningSourceType,
    BulkScreeningWorkItem,
    Document,
    DocumentPurpose,
    Job,
    JobRubricVersion,
    Role,
    RubricVersionStatus,
    User,
)
from app.services.audit import record_audit
from app.services.documents import LocalDocumentStorage, store_bytes, store_upload
from app.services.rubric_utils import rubric_payload_hash
from app.services.screening import (
    EngineProviderError,
    ProviderExecutionResult,
    _engine_command,
    _engine_environment,
    _engine_git_commit,
    _failure_code,
    _run_command,
    _safe_failure_message,
)
from app.services.structured_jd_contract import (
    DESIGNATION_OPTIONS,
    designation_options_for_structured_jd,
    validate_structured_jd_for_engine,
)
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

BULK_STAFF_ROLES = {Role.HR_RECRUITER, Role.DEPARTMENT_REVIEWER, Role.HIRING_ADMIN}
SUPPORTED_BULK_JD_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
SUPPORTED_BULK_RESUME_EXTENSIONS = {".pdf"}
INTEGRATION_BULK_RESUME_EXTENSIONS = {".json"}
SUPPORTED_BULK_ARCHIVE_EXTENSIONS = {".zip"}
UNSUPPORTED_AUDITED_EXTENSIONS = {".doc", ".rtf", ".tif", ".tiff", ".heic", ".jpg", ".jpeg", ".png", ".docx", ".txt"}

logger = logging.getLogger(__name__)

BULK_PROCESSING_STAGE_PROGRESS = {
    "QUEUED": 0,
    "READING_RESUME": 15,
    "STRUCTURING_PROFILE": 45,
    "COMPARING_WITH_JD": 75,
    "COMPLETED": 100,
}
ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class BulkUploadCandidate:
    original_filename: str
    data: bytes
    content_type: str


@dataclass(frozen=True)
class BulkVariantEvaluation:
    designation: str | None
    result: ProviderExecutionResult


class BulkScreeningProvider(Protocol):
    name: str
    engine_version: str

    def evaluate(self, item: BulkScreeningItem, progress: ProgressCallback | None = None) -> ProviderExecutionResult:
        ...


class MockBulkScreeningProvider:
    name = "mock"
    engine_version = "mock-bulk-screening-v1"

    def evaluate(self, item: BulkScreeningItem, progress: ProgressCallback | None = None) -> ProviderExecutionResult:
        if progress:
            progress("READING_RESUME")
        document = item.resume_document
        if document is None:
            raise EngineProviderError("DOCUMENT_NOT_FOUND", "Bulk screening item has no stored resume")
        data = LocalDocumentStorage().resolve_path(document).read_bytes().lower()
        if progress:
            progress("STRUCTURING_PROFILE")
        criteria = item.batch.criteria_snapshot or [
            {"criterion_id": "required", "name": "Required evidence", "category": "skill", "weight": 100}
        ]
        if progress:
            progress("COMPARING_WITH_JD")
        if b"provider failure" in data:
            raise EngineProviderError("ENGINE_EXECUTION_FAILED", "Synthetic provider failure")
        if b"review" in data or b"ambiguous" in data:
            eligibility = "REVIEW"
            fraction = 0.5
            status = "unclear"
            evidence_status = "partially_supported"
            missing = ["Ambiguous evidence requires human review."]
        elif b"missing" in data or b"fail" in data:
            eligibility = "FAIL"
            fraction = 0.0
            status = "not_met"
            evidence_status = "unsupported"
            missing = ["Mandatory requirement evidence was not found."]
        else:
            eligibility = "PASS"
            fraction = 1.0
            status = "met"
            evidence_status = "supported"
            missing = []

        failed_requirement_ids: list[str] = []
        failed_requirement_details: list[dict[str, str]] = []
        evaluations = []
        for criterion in criteria:
            name = criterion.get("name") or criterion.get("criterion_id", "Criterion")
            weight = float(criterion.get("weight") or 0)
            requirement_ids = [str(value) for value in criterion.get("requirement_ids", [])]
            if eligibility == "FAIL":
                failure_id = requirement_ids[0] if requirement_ids else str(criterion.get("criterion_id", "criterion"))
                failed_requirement_ids.append(failure_id)
                failed_requirement_details.append(
                    {
                        "requirement_id": failure_id,
                        "status": "not_met",
                        "description": f"Mandatory evidence missing for {name}.",
                    }
                )
            evaluations.append(
                {
                    "criterion_id": criterion.get("criterion_id", "criterion"),
                    "criterion_name": name,
                    "category": criterion.get("category", "skill"),
                    "weight": weight,
                    "requirement_ids": requirement_ids,
                    "match_fraction": fraction,
                    "weighted_score": round(weight * fraction, 2),
                    "status": status,
                    "explanation": "Synthetic bulk screening evidence generated from uploaded resume content.",
                    "candidate_requirement": name,
                    "evidence_found": [f"Evidence state for {name}."],
                    "missing_information": missing,
                    "ambiguity": missing if eligibility == "REVIEW" else [],
                    "verification_needed": [],
                    "component_assessment": {
                        "supported_core_components": [name] if eligibility == "PASS" else [],
                        "supported_preferred_components": [],
                        "supported_evaluation_dimensions": [],
                        "supported_controlled_equivalents": [],
                        "supported_adjacent_components": [],
                        "missing_core_components": [name] if eligibility == "FAIL" else [],
                        "missing_preferred_components": [],
                        "missing_evaluation_dimensions": [],
                    },
                    "evidence": [
                        {
                            "source_type": "resume",
                            "source_document_id": document.id,
                            "page_number": 1,
                            "block_index": 0,
                            "exact_text": f"Synthetic evidence for {name}.",
                            "normalized_text": f"synthetic evidence for {name.lower()}",
                            "evidence_status": evidence_status,
                            "notes": "Mock provider output, not an employment decision.",
                        }
                    ],
                }
            )
        score = round(sum(item["weighted_score"] for item in evaluations), 2)
        return ProviderExecutionResult(
            provider=self.name,
            provider_engine_version=self.engine_version,
            model_endpoint_slot="mock",
            payload={
                "artifact_schema_version": "candidate-evaluation-v1",
                "evaluation_id": item.id,
                "candidate_id": item.id,
                "job_id": item.batch.job_id or item.batch.id,
                "scoring_version": "mock-bulk-screening-contract-v1",
                "warnings": ["Mock provider. Do not use for real candidate decisions."],
                "eligibility": {
                    "status": eligibility,
                    "checked_requirements": [],
                    "failed_requirements": failed_requirement_ids,
                    "ambiguous_requirements": missing if eligibility == "REVIEW" else [],
                    "requirement_statuses": {},
                    "requirement_details": failed_requirement_details,
                    "explanation": "Synthetic eligibility for bulk workflow testing.",
                },
                "criterion_evaluations": evaluations,
                "score_before_gates": score,
                "final_score": score,
                "maximum_score": 100.0,
                "evidence_completeness": 0.5 if eligibility == "REVIEW" else 0.9,
                "experience_summary": {"confirmed_months": 32 if eligibility == "PASS" else 0, "uncertain_ranges": []},
                "strengths": ["Required evidence is present"] if eligibility == "PASS" else [],
                "gaps": ["Mandatory evidence is missing"] if eligibility == "FAIL" else [],
                "missing_information": missing,
                "recommendation_label": "Human Review",
                "human_review_required": True,
            },
        )


class HiringScreeningEngineBulkProvider:
    name = "hiring-screening-engine"
    engine_version = "screening-v1"

    def evaluate(self, item: BulkScreeningItem, progress: ProgressCallback | None = None) -> ProviderExecutionResult:
        if not item.batch.criteria_snapshot:
            raise EngineProviderError("RUBRIC_NOT_APPROVED", "Bulk screening requires confirmed screening criteria")
        if not item.resume_document:
            raise EngineProviderError("DOCUMENT_NOT_FOUND", "Bulk screening requires a stored resume document")
        structured_jd_variants = _structured_jd_variants_for_batch(item.batch)
        if not structured_jd_variants:
            raise EngineProviderError("RUBRIC_NOT_APPROVED", "Bulk screening requires a StructuredJD payload")

        settings = get_settings()
        engine_root = Path(settings.screening_engine_root).expanduser().resolve()
        if not engine_root.is_dir():
            raise EngineProviderError("ENGINE_CONFIGURATION_ERROR", "Screening engine root does not exist")
        output_root = Path(settings.screening_output_root).expanduser().resolve()
        run_dir = output_root / "bulk" / item.id
        run_dir.mkdir(parents=True, exist_ok=True)
        structured_resume_path = run_dir / "structured-resume.json"

        resume_path = LocalDocumentStorage().resolve_path(item.resume_document)
        primary_env = _engine_environment(settings, gemma_base_url=settings.screening_gemma_base_url)
        model_endpoint_slot: str | None = None
        if resume_path.suffix.lower() == ".json":
            if progress:
                progress("READING_RESUME")
            structured_resume_path.write_bytes(resume_path.read_bytes())
        elif resume_path.suffix.lower() == ".pdf":
            if progress:
                progress("READING_RESUME")
            ocr_dir = run_dir / "ocr"
            _run_bulk_engine_stage(
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
                batch_id=item.batch.id,
                item_id=item.id,
                stage="ocr",
            )
            if progress:
                progress("STRUCTURING_PROFILE")
            model_endpoint_slot = self._structure_resume_with_gemma_fallback(
                settings=settings,
                engine_root=engine_root,
                ocr_dir=ocr_dir,
                structured_resume_path=structured_resume_path,
                candidate_id=item.id,
                batch_id=item.batch.id,
                item_id=item.id,
            )
        else:
            raise EngineProviderError("ENGINE_CONFIGURATION_ERROR", "Real bulk provider supports JSON or PDF resumes")

        if progress:
            progress("COMPARING_WITH_JD")
        eval_env = _engine_environment(
            settings,
            gemma_base_url=(
                settings.screening_gemma_fallback_base_url
                if model_endpoint_slot == "fallback" and settings.screening_gemma_fallback_base_url
                else settings.screening_gemma_base_url
            ),
        )
        results = [
            self._evaluate_structured_resume_variant(
                item=item,
                settings=settings,
                engine_root=engine_root,
                run_dir=run_dir,
                structured_resume_path=structured_resume_path,
                structured_jd=structured_jd,
                designation=designation,
                index=index,
                env=eval_env,
                model_endpoint_slot=model_endpoint_slot,
            )
            for index, (designation, structured_jd) in enumerate(structured_jd_variants, start=1)
        ]
        selected = _strongest_variant_result(results)
        payload = dict(selected.result.payload)
        if len(results) > 1:
            payload["bulk_designation_evaluation"] = {
                "selected_designation": selected.designation,
                "evaluated_designations": [result.designation for result in results],
                "aggregation_rule": "meets_else_review_else_does_not_meet",
            }
            payload["warnings"] = [
                *[str(warning) for warning in payload.get("warnings", [])],
                "Multiple JD designation variants were evaluated from the same structured resume.",
            ]
        return ProviderExecutionResult(
            provider=self.name,
            provider_engine_version=self.engine_version,
            payload=payload,
            model_endpoint_slot=model_endpoint_slot,
            raw_result_ref=selected.result.raw_result_ref,
            structured_jd_path=selected.result.structured_jd_path,
            structured_resume_path=structured_resume_path,
            engine_code_version=_engine_git_commit(engine_root, settings),
        )

    def _evaluate_structured_resume_variant(
        self,
        *,
        item: BulkScreeningItem,
        settings,
        engine_root: Path,
        run_dir: Path,
        structured_resume_path: Path,
        structured_jd: dict[str, Any],
        designation: str | None,
        index: int,
        env: dict[str, str],
        model_endpoint_slot: str | None,
    ) -> BulkVariantEvaluation:
        suffix = _designation_artifact_suffix(designation) if designation else "single"
        structured_jd_path = run_dir / f"structured-jd-{suffix}.json"
        evaluation_path = run_dir / f"evaluation-{suffix}.json"
        structured_jd_path.write_text(json.dumps(structured_jd, indent=2), encoding="utf-8")
        _run_bulk_engine_stage(
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
            env=env,
            failure_code="ENGINE_EXECUTION_FAILED",
            batch_id=item.batch.id,
            item_id=item.id,
            stage=f"candidate_evaluation_{index}",
            model_endpoint_slot=model_endpoint_slot,
        )
        if not evaluation_path.is_file():
            raise EngineProviderError("ENGINE_OUTPUT_MISSING", "Engine evaluation artifact was not created")
        try:
            payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise EngineProviderError(
                "ENGINE_OUTPUT_INVALID",
                "Engine evaluation artifact is not valid JSON",
            ) from error
        return BulkVariantEvaluation(
            designation=designation,
            result=ProviderExecutionResult(
                provider=self.name,
                provider_engine_version=self.engine_version,
                payload=payload,
                model_endpoint_slot=model_endpoint_slot,
                raw_result_ref=f"{Path(settings.screening_output_root).name}/bulk/{item.id}/{evaluation_path.name}",
                structured_jd_path=structured_jd_path,
                structured_resume_path=structured_resume_path,
                engine_code_version=_engine_git_commit(engine_root, settings),
            ),
        )

    def _structure_resume_with_gemma_fallback(
        self,
        *,
        settings,
        engine_root: Path,
        ocr_dir: Path,
        structured_resume_path: Path,
        candidate_id: str,
        batch_id: str,
        item_id: str,
    ) -> str:
        slots = [("primary", settings.screening_gemma_base_url)]
        if settings.screening_gemma_fallback_base_url:
            slots.append(("fallback", settings.screening_gemma_fallback_base_url))
        last_error: EngineProviderError | None = None
        for slot, gemma_base_url in slots:
            try:
                _run_bulk_engine_stage(
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
                    batch_id=batch_id,
                    item_id=item_id,
                    stage="resume_structuring",
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


def supported_bulk_formats() -> dict[str, list[str]]:
    return {
        "jd": sorted(SUPPORTED_BULK_JD_EXTENSIONS),
        "resumes": sorted(SUPPORTED_BULK_RESUME_EXTENSIONS),
        "archives": sorted(SUPPORTED_BULK_ARCHIVE_EXTENSIONS),
        "unsupported": sorted(UNSUPPORTED_AUDITED_EXTENSIONS),
        "notes": [
            "HR-facing resume support is limited to PDF because the current real provider executes PDF resumes "
            "end-to-end through OCR, Gemma structuring, and deterministic evaluation.",
            "Structured JSON resumes remain an integration/test capability and are not advertised as normal HR upload.",
            "DOC, RTF, TIFF, HEIC, JPG, JPEG, PNG, DOCX, and TXT resumes are not advertised for bulk screening until "
            "the complete real pipeline supports them.",
            "JD upload supports PDF, DOCX, TXT, and MD through the current JD extraction path.",
        ],
    }


def _run_bulk_engine_stage(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
    failure_code: str,
    batch_id: str,
    item_id: str,
    stage: str,
    model_endpoint_slot: str | None = None,
):
    logger.info("bulk_work_item_stage_started batch_id=%s item_id=%s stage=%s", batch_id, item_id, stage)
    started = time.monotonic()
    try:
        completed = _run_command(
            command,
            cwd=cwd,
            timeout=timeout,
            env=env,
            failure_code=failure_code,
            model_endpoint_slot=model_endpoint_slot,
        )
    except Exception:
        logger.exception(
            "bulk_work_item_stage_failed batch_id=%s item_id=%s stage=%s elapsed_seconds=%.3f",
            batch_id,
            item_id,
            stage,
            time.monotonic() - started,
        )
        raise
    logger.info(
        "bulk_work_item_stage_completed batch_id=%s item_id=%s stage=%s elapsed_seconds=%.3f",
        batch_id,
        item_id,
        stage,
        time.monotonic() - started,
    )
    return completed


def list_batches(db: Session, actor: User) -> list[BulkScreeningBatch]:
    require_any_role(actor, BULK_STAFF_ROLES)
    return list(
        db.scalars(
            select(BulkScreeningBatch)
            .where(BulkScreeningBatch.archived_at.is_(None))
            .order_by(BulkScreeningBatch.created_at.desc())
        )
    )


def get_batch(db: Session, actor: User, batch_id: str) -> BulkScreeningBatch:
    require_any_role(actor, BULK_STAFF_ROLES)
    batch = db.get(BulkScreeningBatch, batch_id)
    if batch is None:
        raise NotFound("Bulk screening batch not found")
    return batch


def create_existing_job_batch(
    db: Session,
    actor: User,
    *,
    job_id: str,
    files: list[UploadFile] | None = None,
    zip_file: UploadFile | None = None,
) -> BulkScreeningBatch:
    require_any_role(actor, BULK_STAFF_ROLES)
    job = db.get(Job, job_id)
    if job is None:
        raise NotFound("Job not found")
    rubric_version = _current_approved_rubric(job)
    if rubric_version is None:
        raise InvalidTransition("Bulk screening requires the job's current approved rubric version")
    target_designation = job.designation if job.designation in DESIGNATION_OPTIONS else None
    _structured_jd_variants_for_payload(rubric_version.structured_jd_payload, target_designation=target_designation)
    batch = BulkScreeningBatch(
        created_by=actor,
        source_type=BulkScreeningSourceType.EXISTING_JOB,
        job=job,
        rubric_version=rubric_version,
        criteria_snapshot=rubric_version.criteria,
        target_designation=target_designation,
        title=f"{job.title} bulk screening",
        status=BulkScreeningBatchStatus.READY,
    )
    db.add(batch)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        action="bulk_screening.batch_create",
        entity_type="bulk_screening_batch",
        entity_id=batch.id,
        remarks=f"source=existing_job job={job.id} rubric_version={rubric_version.id}",
    )
    if files or zip_file:
        _ingest_resume_uploads(db, actor, batch, files=files, zip_file=zip_file)
    return batch


def create_ad_hoc_jd_batch(db: Session, actor: User, *, jd_file: UploadFile) -> BulkScreeningBatch:
    require_any_role(actor, BULK_STAFF_ROLES)
    document = store_upload(db, actor, jd_file, DocumentPurpose.JOB_JD)
    structured_jd = _generate_ad_hoc_structured_jd(document)
    criteria = structured_jd.get("scoring_rubric") or []
    if not criteria:
        raise InvalidTransition("Ad-hoc JD extraction did not produce screening criteria")
    batch = BulkScreeningBatch(
        created_by=actor,
        source_type=BulkScreeningSourceType.ADHOC_JD,
        ad_hoc_jd_document=document,
        ad_hoc_structured_jd=structured_jd,
        ad_hoc_structured_jd_sha256=_hash_json(structured_jd),
        criteria_snapshot=criteria,
        title=f"{structured_jd.get('job_title') or document.original_filename} bulk screening",
        status=BulkScreeningBatchStatus.DRAFT,
    )
    db.add(batch)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        action="bulk_screening.adhoc_jd_uploaded",
        entity_type="bulk_screening_batch",
        entity_id=batch.id,
        remarks=f"document={document.id} structured_jd_sha256={batch.ad_hoc_structured_jd_sha256}",
    )
    return batch


def create_simple_ad_hoc_screening_batch(
    db: Session,
    actor: User,
    *,
    jd_file: UploadFile,
    files: list[UploadFile] | None = None,
    zip_file: UploadFile | None = None,
    target_designation: str | None = None,
) -> BulkScreeningBatch:
    batch = create_ad_hoc_jd_batch(db, actor, jd_file=jd_file)
    try:
        confirm_ad_hoc_criteria(db, actor, batch.id, target_designation=target_designation)
    except StructuredDomainError as error:
        if error.code != "INVALID_SCREENING_CRITERIA":
            raise
        reconcile_ad_hoc_criteria(db, actor, batch.id, target_designation=target_designation)
        confirm_ad_hoc_criteria(db, actor, batch.id, target_designation=target_designation)
    add_resumes_to_batch(db, actor, batch.id, files=files, zip_file=zip_file)
    return start_batch(db, actor, batch.id)


def confirm_ad_hoc_criteria(
    db: Session,
    actor: User,
    batch_id: str,
    *,
    target_designation: str | None = None,
) -> BulkScreeningBatch:
    batch = get_batch(db, actor, batch_id)
    if batch.source_type != BulkScreeningSourceType.ADHOC_JD:
        raise InvalidTransition("Only ad-hoc JD batches require criteria confirmation")
    if not batch.ad_hoc_structured_jd or not batch.criteria_snapshot:
        raise InvalidTransition("Ad-hoc JD criteria are not available")
    batch.target_designation = target_designation or batch.target_designation
    _validate_structured_jd_confirmation(
        batch.ad_hoc_structured_jd,
        batch.criteria_snapshot,
        target_designation=batch.target_designation,
    )
    batch.criteria_confirmed_by = actor
    batch.criteria_confirmed_at = utcnow()
    batch.status = BulkScreeningBatchStatus.READY
    record_audit(
        db,
        actor_id=actor.id,
        action="bulk_screening.criteria_confirm",
        entity_type="bulk_screening_batch",
        entity_id=batch.id,
        remarks=f"structured_jd_sha256={batch.ad_hoc_structured_jd_sha256}",
    )
    return batch


def reconcile_ad_hoc_criteria(
    db: Session,
    actor: User,
    batch_id: str,
    *,
    target_designation: str | None = None,
) -> BulkScreeningBatch:
    batch = get_batch(db, actor, batch_id)
    if batch.source_type != BulkScreeningSourceType.ADHOC_JD:
        raise InvalidTransition("Only ad-hoc JD batches can reconcile extracted criteria")
    if batch.status != BulkScreeningBatchStatus.DRAFT:
        raise InvalidTransition("Only draft ad-hoc JD criteria can be reconciled")
    if not batch.ad_hoc_structured_jd or not batch.criteria_snapshot:
        raise InvalidTransition("Ad-hoc JD criteria are not available")
    batch.target_designation = target_designation or batch.target_designation
    mandatory_ids = {
        requirement.get("requirement_id") or requirement.get("id")
        for requirement in batch.ad_hoc_structured_jd.get("mandatory_requirements", [])
        if isinstance(requirement, dict) and (requirement.get("requirement_id") or requirement.get("id"))
    }
    reconciled = []
    criteria = []
    for criterion in batch.criteria_snapshot:
        next_criterion = dict(criterion)
        linked_ids = set(next_criterion.get("requirement_ids") or [])
        if linked_ids & mandatory_ids and next_criterion.get("mandatory") is not True:
            next_criterion["mandatory"] = True
            reconciled.append(str(next_criterion.get("criterion_id") or next_criterion.get("name")))
        criteria.append(next_criterion)
    if not reconciled:
        raise InvalidTransition("No deterministic ad-hoc criteria reconciliation is available")
    batch.criteria_snapshot = criteria
    flag_modified(batch, "criteria_snapshot")
    _validate_structured_jd_confirmation(
        batch.ad_hoc_structured_jd,
        criteria,
        target_designation=batch.target_designation,
    )
    record_audit(
        db,
        actor_id=actor.id,
        action="bulk_screening.criteria_reconcile",
        entity_type="bulk_screening_batch",
        entity_id=batch.id,
        remarks=f"mandatory_criteria={','.join(reconciled)} target_designation={batch.target_designation}",
    )
    return batch


def add_resumes_to_batch(
    db: Session,
    actor: User,
    batch_id: str,
    *,
    files: list[UploadFile] | None = None,
    zip_file: UploadFile | None = None,
) -> BulkScreeningBatch:
    batch = get_batch(db, actor, batch_id)
    if batch.status != BulkScreeningBatchStatus.READY:
        raise InvalidTransition("Batch must have confirmed screening criteria before resume upload")
    _ingest_resume_uploads(db, actor, batch, files=files, zip_file=zip_file)
    return batch


def start_batch(db: Session, actor: User, batch_id: str) -> BulkScreeningBatch:
    batch = get_batch(db, actor, batch_id)
    if batch.status != BulkScreeningBatchStatus.READY:
        raise InvalidTransition("Only a reviewed, ready batch can be started")
    if batch.source_type == BulkScreeningSourceType.ADHOC_JD and not batch.criteria_confirmed_at:
        raise InvalidTransition("Confirm ad-hoc JD criteria before screening resumes")
    _structured_jd_variants_for_batch(batch)
    queueable = [
        item
        for item in batch.items
        if item.status == BulkScreeningItemStatus.PENDING and item.resume_document_id and item.work_item is None
    ]
    if not queueable:
        raise InvalidTransition("Batch has no validated unique resumes ready to screen")
    for item in queueable:
        item.processing_stage = "QUEUED"
        item.progress_percent = 0
        item.stage_updated_at = utcnow()
        db.add(
            BulkScreeningWorkItem(
                item=item,
                status=BulkScreeningItemStatus.PENDING,
                processing_stage="QUEUED",
                progress_percent=0,
                stage_updated_at=item.stage_updated_at,
                max_attempts=get_settings().screening_worker_max_attempts,
            )
        )
    batch.status = BulkScreeningBatchStatus.QUEUED
    batch.started_at = batch.started_at or utcnow()
    batch.failure_code = None
    batch.failure_message = None
    record_audit(
        db,
        actor_id=actor.id,
        action="bulk_screening.start",
        entity_type="bulk_screening_batch",
        entity_id=batch.id,
        remarks=f"queued_items={len(queueable)}",
    )
    _refresh_batch_counts(batch)
    return batch


def discard_draft_batch(db: Session, actor: User, batch_id: str) -> None:
    batch = get_batch(db, actor, batch_id)
    if batch.status not in {BulkScreeningBatchStatus.DRAFT, BulkScreeningBatchStatus.READY}:
        raise InvalidTransition("Only unstarted draft or ready bulk screening batches can be discarded")
    if any(item.work_item is not None for item in batch.items):
        raise InvalidTransition("Bulk screening batch has already been queued and cannot be discarded")
    record_audit(
        db,
        actor_id=actor.id,
        action="bulk_screening.discard_draft",
        entity_type="bulk_screening_batch",
        entity_id=batch.id,
        remarks=f"status={batch.status.value} total_files={batch.total_files}",
    )
    db.delete(batch)


def archive_batch(db: Session, actor: User, batch_id: str) -> BulkScreeningBatch:
    batch = get_batch(db, actor, batch_id)
    if batch.status in {BulkScreeningBatchStatus.DRAFT, BulkScreeningBatchStatus.READY}:
        raise InvalidTransition("Unstarted bulk screening batches should be discarded instead of archived")
    if batch.status in {BulkScreeningBatchStatus.QUEUED, BulkScreeningBatchStatus.RUNNING}:
        raise InvalidTransition("Running bulk screening batches cannot be archived because cancellation is unsupported")
    if batch.status not in {BulkScreeningBatchStatus.COMPLETED, BulkScreeningBatchStatus.FAILED}:
        raise InvalidTransition("Only completed or failed bulk screening batches can be archived")
    if batch.archived_at is None:
        batch.archived_at = utcnow()
        batch.archived_by = actor
        record_audit(
            db,
            actor_id=actor.id,
            action="bulk_screening.archive",
            entity_type="bulk_screening_batch",
            entity_id=batch.id,
            remarks=f"status={batch.status.value} completed={batch.completed_count} failed={batch.failed_count}",
        )
    return batch


def resume_failed_batch(db: Session, actor: User, batch_id: str) -> BulkScreeningBatch:
    batch = get_batch(db, actor, batch_id)
    if batch.status != BulkScreeningBatchStatus.FAILED:
        raise InvalidTransition("Only failed bulk screening batches can be resumed")
    _structured_jd_variants_for_batch(batch)
    reset_count = 0
    for item in batch.items:
        if item.status == BulkScreeningItemStatus.COMPLETED:
            continue
        if item.status == BulkScreeningItemStatus.FAILED and not _is_retriable_bulk_failure(item.failure_code):
            continue
        if not item.resume_document_id:
            continue
        item.status = BulkScreeningItemStatus.PENDING
        item.classification = None
        item.concise_reason = None
        item.failure_code = None
        item.failure_message = None
        item.failed_at = None
        item.processing_stage = "QUEUED"
        item.progress_percent = 0
        item.stage_updated_at = utcnow()
        if item.work_item:
            item.work_item.status = BulkScreeningItemStatus.PENDING
            item.work_item.attempts = 0
            item.work_item.processing_stage = "QUEUED"
            item.work_item.progress_percent = 0
            item.work_item.stage_updated_at = item.stage_updated_at
            item.work_item.locked_at = None
            item.work_item.started_at = None
            item.work_item.completed_at = None
            item.work_item.failed_at = None
            item.work_item.failure_code = None
            item.work_item.failure_message = None
        else:
            db.add(
                BulkScreeningWorkItem(
                    item=item,
                    status=BulkScreeningItemStatus.PENDING,
                    processing_stage="QUEUED",
                    progress_percent=0,
                    stage_updated_at=item.stage_updated_at,
                    max_attempts=get_settings().screening_worker_max_attempts,
                )
            )
        reset_count += 1
    if reset_count == 0:
        raise InvalidTransition("This failed batch has no retryable pending or technical-failure items")
    batch.status = BulkScreeningBatchStatus.QUEUED
    batch.failure_code = None
    batch.failure_message = None
    batch.completed_at = None
    record_audit(
        db,
        actor_id=actor.id,
        action="bulk_screening.resume_failed_batch",
        entity_type="bulk_screening_batch",
        entity_id=batch.id,
        remarks=f"requeued_items={reset_count}",
    )
    _refresh_batch_counts(batch)
    return batch


def process_next_bulk_screening_jobs(
    db: Session,
    *,
    provider: BulkScreeningProvider | None = None,
    limit: int | None = None,
) -> int:
    limit = max(1, limit or get_settings().bulk_screening_worker_batch_size)
    jobs = list(
        db.scalars(
            select(BulkScreeningWorkItem)
            .join(BulkScreeningWorkItem.item)
            .join(BulkScreeningItem.batch)
            .where(BulkScreeningWorkItem.status == BulkScreeningItemStatus.PENDING)
            .where(BulkScreeningBatch.status.in_([BulkScreeningBatchStatus.QUEUED, BulkScreeningBatchStatus.RUNNING]))
            .order_by(BulkScreeningWorkItem.created_at)
            .limit(limit)
        )
    )
    for job in jobs:
        process_bulk_screening_job(db, job, provider=provider)
    return len(jobs)


def process_bulk_screening_job(
    db: Session,
    job: BulkScreeningWorkItem,
    *,
    provider: BulkScreeningProvider | None = None,
) -> BulkScreeningWorkItem:
    provider = provider or _bulk_provider_from_settings()
    item = job.item
    batch = item.batch
    actor = batch.created_by
    logger.info("bulk_screening.item_claimed batch_id=%s item_id=%s attempt=%s", batch.id, item.id, job.attempts + 1)
    job.status = BulkScreeningItemStatus.RUNNING
    job.locked_at = utcnow()
    job.started_at = utcnow()
    job.attempts += 1
    item.status = BulkScreeningItemStatus.RUNNING
    item.started_at = utcnow()
    batch.status = BulkScreeningBatchStatus.RUNNING
    _set_bulk_processing_stage(db, job, "READING_RESUME", commit=True)
    logger.info("bulk_screening.item_started batch_id=%s item_id=%s provider=%s", batch.id, item.id, provider.name)
    try:
        result = _evaluate_bulk_provider(
            provider,
            item,
            progress=lambda stage: _set_bulk_processing_stage(db, job, stage, commit=True),
        )
        _apply_bulk_result(item, result)
        _set_bulk_processing_stage(db, job, "COMPLETED", commit=False)
        item.status = BulkScreeningItemStatus.COMPLETED
        item.completed_at = utcnow()
        job.status = BulkScreeningItemStatus.COMPLETED
        job.completed_at = utcnow()
        record_audit(
            db,
            actor_id=actor.id,
            action="bulk_screening.item_complete",
            entity_type="bulk_screening_item",
            entity_id=item.id,
            remarks=f"classification={item.classification}",
        )
        logger.info(
            "bulk_screening.item_completed batch_id=%s item_id=%s classification=%s",
            batch.id,
            item.id,
            item.classification.value if item.classification else None,
        )
    except Exception as error:
        message = _safe_failure_message(error)
        failure_code = _failure_code(error)
        logger.exception(
            "bulk_screening.item_failed batch_id=%s item_id=%s failure_code=%s",
            batch.id,
            item.id,
            failure_code,
        )
        if _is_systemic_bulk_failure(failure_code):
            item.status = BulkScreeningItemStatus.FAILED
            item.classification = BulkScreeningClassification.NEEDS_REVIEW
            item.concise_reason = "Screening stopped because the batch configuration needs technical review."
            item.failed_at = utcnow()
            item.failure_code = failure_code
            item.failure_message = message
            item.progress_percent = 100
            item.provider = getattr(provider, "name", None)
            item.provider_engine_version = getattr(provider, "engine_version", None)
            job.status = BulkScreeningItemStatus.FAILED
            job.failed_at = utcnow()
            job.failure_code = failure_code
            job.failure_message = message
            job.progress_percent = 100
            batch.status = BulkScreeningBatchStatus.FAILED
            batch.completed_at = batch.completed_at or utcnow()
            batch.failure_code = failure_code
            batch.failure_message = message
            record_audit(
                db,
                actor_id=actor.id,
                action="bulk_screening.systemic_fail",
                entity_type="bulk_screening_batch",
                entity_id=batch.id,
                remarks=f"{failure_code}: {message}",
            )
        elif job.attempts < job.max_attempts:
            item.status = BulkScreeningItemStatus.PENDING
            item.processing_stage = "QUEUED"
            item.progress_percent = 0
            item.stage_updated_at = utcnow()
            job.status = BulkScreeningItemStatus.PENDING
            job.processing_stage = "QUEUED"
            job.progress_percent = 0
            job.stage_updated_at = item.stage_updated_at
            job.failure_code = failure_code
            job.failure_message = message
            record_audit(
                db,
                actor_id=actor.id,
                action="bulk_screening.item_retry_pending",
                entity_type="bulk_screening_item",
                entity_id=item.id,
                remarks=f"{failure_code}: {message}",
            )
            logger.warning(
                "bulk_screening.item_failed_retry_pending batch_id=%s item_id=%s failure_code=%s attempt=%s",
                batch.id,
                item.id,
                failure_code,
                job.attempts,
            )
        else:
            item.status = BulkScreeningItemStatus.FAILED
            item.classification = BulkScreeningClassification.NEEDS_REVIEW
            item.concise_reason = "Screening could not be completed because of a technical processing failure."
            item.failed_at = utcnow()
            item.failure_code = failure_code
            item.failure_message = message
            item.progress_percent = 100
            item.provider = getattr(provider, "name", None)
            item.provider_engine_version = getattr(provider, "engine_version", None)
            job.status = BulkScreeningItemStatus.FAILED
            job.failed_at = utcnow()
            job.failure_code = item.failure_code
            job.failure_message = message
            job.progress_percent = 100
            record_audit(
                db,
                actor_id=actor.id,
                action="bulk_screening.item_fail",
                entity_type="bulk_screening_item",
                entity_id=item.id,
                remarks=f"{item.failure_code}: {message}",
            )
    _refresh_batch_counts(batch)
    if batch.status in {BulkScreeningBatchStatus.COMPLETED, BulkScreeningBatchStatus.FAILED}:
        logger.info(
            "bulk_screening.batch_completed batch_id=%s status=%s completed=%s failed=%s",
            batch.id,
            batch.status.value,
            batch.completed_count,
            batch.failed_count,
        )
    return job


def batch_to_read(batch: BulkScreeningBatch, *, include_items: bool = True) -> dict[str, Any]:
    payload = {
        "id": batch.id,
        "created_by_id": batch.created_by_id,
        "source_type": batch.source_type,
        "job_id": batch.job_id,
        "rubric_version_id": batch.rubric_version_id,
        "ad_hoc_jd_document_id": batch.ad_hoc_jd_document_id,
        "ad_hoc_structured_jd": batch.ad_hoc_structured_jd,
        "ad_hoc_structured_jd_sha256": batch.ad_hoc_structured_jd_sha256,
        "criteria_snapshot": batch.criteria_snapshot,
        "target_designation": batch.target_designation,
        "criteria_confirmed_by_id": batch.criteria_confirmed_by_id,
        "criteria_confirmed_at": batch.criteria_confirmed_at,
        "title": batch.title,
        "status": batch.status,
        "total_files": batch.total_files,
        "accepted_count": batch.accepted_count,
        "duplicate_count": batch.duplicate_count,
        "unsupported_count": batch.unsupported_count,
        "completed_count": batch.completed_count,
        "failed_count": batch.failed_count,
        "progress_percent": batch.progress_percent,
        "failure_code": batch.failure_code,
        "failure_message": safe_bulk_failure_message(batch.failure_code, batch.failure_message),
        "started_at": batch.started_at,
        "completed_at": batch.completed_at,
        "archived_at": batch.archived_at,
        "archived_by_id": batch.archived_by_id,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
        "job_title": batch.job.title if batch.job else None,
        "jd_document": batch.ad_hoc_jd_document,
    }
    if include_items:
        payload["items"] = [item_to_read(item) for item in batch.items]
    return payload


def batch_to_summary(batch: BulkScreeningBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "source_type": batch.source_type,
        "job_id": batch.job_id,
        "rubric_version_id": batch.rubric_version_id,
        "target_designation": batch.target_designation,
        "title": batch.title,
        "status": batch.status,
        "total_files": batch.total_files,
        "accepted_count": batch.accepted_count,
        "duplicate_count": batch.duplicate_count,
        "unsupported_count": batch.unsupported_count,
        "completed_count": batch.completed_count,
        "failed_count": batch.failed_count,
        "progress_percent": batch.progress_percent,
        "failure_code": batch.failure_code,
        "failure_message": safe_bulk_failure_message(batch.failure_code, batch.failure_message),
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
        "archived_at": batch.archived_at,
        "archived_by_id": batch.archived_by_id,
        "job_title": batch.job.title if batch.job else None,
    }


def item_to_read(item: BulkScreeningItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "batch_id": item.batch_id,
        "resume_document_id": item.resume_document_id,
        "original_filename": item.original_filename,
        "content_sha256": item.content_sha256,
        "duplicate_of_item_id": item.duplicate_of_item_id,
        "status": item.status,
        "processing_stage": item.processing_stage,
        "progress_percent": item.progress_percent,
        "stage_updated_at": item.stage_updated_at,
        "classification": item.classification,
        "concise_reason": item.concise_reason,
        "candidate_name": item.candidate_name,
        "provider": item.provider,
        "provider_engine_version": item.provider_engine_version,
        "engine_contract_version": item.engine_contract_version,
        "engine_artifact_schema_version": item.engine_artifact_schema_version,
        "engine_code_version": item.engine_code_version,
        "model_endpoint_slot": item.model_endpoint_slot,
        "eligibility": item.eligibility,
        "evidence_completeness": item.evidence_completeness,
        "confirmed_experience_months": item.confirmed_experience_months,
        "warnings": item.warnings,
        "failure_code": item.failure_code,
        "failure_message": safe_bulk_failure_message(item.failure_code, item.failure_message),
        "raw_result_ref": item.raw_result_ref,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "failed_at": item.failed_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "criterion_results": [
            {
                "id": result.id,
                "criterion_id": result.criterion_id,
                "criterion_name": result.criterion_name,
                "category": result.category,
                "status": result.status,
                "explanation": result.explanation,
                "candidate_requirement": result.candidate_requirement,
                "evidence_found": result.evidence_found,
                "missing_information": result.missing_information,
                "ambiguity": result.ambiguity,
                "verification_needed": result.verification_needed,
                "matched_terms": result.matched_terms,
                "unmatched_terms": result.unmatched_terms,
                "raw_component_assessment": result.raw_component_assessment,
                "evidence": result.evidence,
            }
            for result in item.criterion_results
        ],
    }


def _ingest_resume_uploads(
    db: Session,
    actor: User,
    batch: BulkScreeningBatch,
    *,
    files: list[UploadFile] | None,
    zip_file: UploadFile | None,
) -> None:
    candidates = []
    for file in files or []:
        candidates.append(
            BulkUploadCandidate(
                original_filename=file.filename or "",
                data=file.file.read(),
                content_type=file.content_type or "application/octet-stream",
            )
        )
    if zip_file is not None:
        candidates.extend(_extract_zip_candidates(zip_file))
    if not candidates:
        raise InvalidTransition("Bulk screening requires at least one resume file")

    existing_by_sha = {
        item.content_sha256: item
        for item in batch.items
        if item.content_sha256 and not item.duplicate_of_item_id
    }
    for candidate in candidates:
        _ingest_resume_candidate(db, actor, batch, candidate, existing_by_sha)
    _refresh_batch_counts(batch)
    record_audit(
        db,
        actor_id=actor.id,
        action="bulk_screening.resumes_uploaded",
        entity_type="bulk_screening_batch",
        entity_id=batch.id,
        remarks=(
            f"files={len(candidates)} accepted={batch.accepted_count} "
            f"duplicates={batch.duplicate_count} unsupported={batch.unsupported_count}"
        ),
    )


def _ingest_resume_candidate(
    db: Session,
    actor: User,
    batch: BulkScreeningBatch,
    candidate: BulkUploadCandidate,
    existing_by_sha: dict[str, BulkScreeningItem],
) -> None:
    filename = _display_filename(candidate.original_filename)
    digest = sha256(candidate.data).hexdigest()
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_BULK_RESUME_EXTENSIONS | INTEGRATION_BULK_RESUME_EXTENSIONS:
        item = BulkScreeningItem(
            batch=batch,
            original_filename=filename,
            content_sha256=digest,
            status=BulkScreeningItemStatus.UNSUPPORTED,
            classification=BulkScreeningClassification.NEEDS_REVIEW,
            concise_reason=f"Unsupported resume file type {suffix or '<none>'}; this file was not screened.",
            failure_code="UNSUPPORTED_FILE_TYPE",
            failure_message=f"Supported resume formats: {', '.join(sorted(SUPPORTED_BULK_RESUME_EXTENSIONS))}",
        )
        db.add(item)
        db.flush()
        return
    duplicate = existing_by_sha.get(digest)
    if duplicate is not None:
        item = BulkScreeningItem(
            batch=batch,
            original_filename=filename,
            content_sha256=digest,
            duplicate_of=duplicate,
            status=BulkScreeningItemStatus.DUPLICATE,
            classification=duplicate.classification,
            concise_reason=f"Duplicate of {duplicate.original_filename}; ignored to avoid repeated OCR/model work.",
        )
        db.add(item)
        db.flush()
        return
    document = store_bytes(
        db,
        actor,
        filename=filename,
        data=candidate.data,
        purpose=DocumentPurpose.RESUME,
        content_type=_content_type_for(filename, candidate.content_type),
    )
    item = BulkScreeningItem(
        batch=batch,
        resume_document=document,
        original_filename=filename,
        content_sha256=digest,
        status=BulkScreeningItemStatus.PENDING,
    )
    db.add(item)
    db.flush()
    existing_by_sha[digest] = item


def _extract_zip_candidates(zip_file: UploadFile) -> list[BulkUploadCandidate]:
    settings = get_settings()
    filename = zip_file.filename or ""
    if Path(filename).suffix.lower() != ".zip":
        raise DomainError("Bulk archive upload must be a .zip file")
    data = zip_file.file.read()
    if len(data) > settings.bulk_screening_max_zip_bytes:
        raise DomainError("ZIP archive exceeds maximum compressed size")
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if len(infos) > settings.bulk_screening_max_zip_files:
                raise DomainError("ZIP archive contains too many files")
            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > settings.bulk_screening_max_zip_uncompressed_bytes:
                raise DomainError("ZIP archive exceeds maximum uncompressed size")
            candidates = []
            seen_names: set[str] = set()
            for info in infos:
                _validate_zip_member(info, seen_names)
                name = _display_filename(info.filename)
                candidates.append(
                    BulkUploadCandidate(
                        original_filename=name,
                        data=archive.read(info),
                        content_type=_content_type_for(name, "application/octet-stream"),
                    )
                )
            return candidates
    except zipfile.BadZipFile as error:
        raise DomainError("ZIP archive is corrupt or unreadable") from error


def _validate_zip_member(info: zipfile.ZipInfo, seen_names: set[str]) -> None:
    pure = PurePosixPath(info.filename)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise DomainError("ZIP archive contains an unsafe path")
    if _is_zip_symlink(info):
        raise DomainError("ZIP archive contains a symlink")
    suffix = Path(info.filename).suffix.lower()
    if suffix in SUPPORTED_BULK_ARCHIVE_EXTENSIONS:
        raise DomainError("Nested ZIP archives are not supported")
    name = _display_filename(info.filename)
    if name in seen_names:
        raise DomainError(f"ZIP archive contains duplicate filename: {name}")
    seen_names.add(name)


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def _apply_bulk_result(item: BulkScreeningItem, result: ProviderExecutionResult) -> None:
    payload = result.payload
    eligibility = (payload.get("eligibility") or {}).get("status")
    item.provider = result.provider
    item.provider_engine_version = result.provider_engine_version
    item.model_endpoint_slot = result.model_endpoint_slot
    item.engine_contract_version = "candidate-evaluation-v1/platform-bulk-mapper-v1"
    item.engine_artifact_schema_version = payload.get("artifact_schema_version")
    item.engine_code_version = result.engine_code_version or payload.get("scoring_version")
    item.eligibility = eligibility
    item.evidence_completeness = payload.get("evidence_completeness")
    item.confirmed_experience_months = (payload.get("experience_summary") or {}).get("confirmed_months")
    item.warnings = payload.get("warnings", [])
    item.raw_result_ref = result.raw_result_ref
    item.raw_result = payload
    item.classification = _classification_from_payload(payload)
    item.concise_reason = _concise_reason(payload, item.classification)
    item.candidate_name = _candidate_name_from_payload(payload, result.structured_resume_path)
    item.criterion_results = [_bulk_criterion_result(item, entry) for entry in payload.get("criterion_evaluations", [])]


def _bulk_criterion_result(item: BulkScreeningItem, entry: dict[str, Any]) -> BulkScreeningCriterionResult:
    component_assessment = entry.get("component_assessment") or {}
    result = BulkScreeningCriterionResult(
        item=item,
        criterion_id=entry.get("criterion_id", ""),
        criterion_name=entry.get("criterion_name") or entry.get("criterion_id", ""),
        category=entry.get("category", ""),
        status=entry.get("status", "unclear"),
        explanation=entry.get("explanation", ""),
        candidate_requirement=entry.get("candidate_requirement", ""),
        evidence_found=entry.get("evidence_found", []),
        missing_information=entry.get("missing_information", []),
        ambiguity=entry.get("ambiguity", []),
        verification_needed=entry.get("verification_needed", []),
        matched_terms=_matched_terms(component_assessment),
        unmatched_terms=_unmatched_terms(component_assessment),
        raw_component_assessment=component_assessment,
    )
    result.evidence = [
        BulkScreeningEvidence(
            source_type=evidence.get("source_type", ""),
            source_document_id=evidence.get("source_document_id", ""),
            page_number=evidence.get("page_number"),
            block_index=evidence.get("block_index"),
            exact_text=evidence.get("exact_text", ""),
            normalized_text=evidence.get("normalized_text"),
            evidence_status=evidence.get("evidence_status", "supported"),
            notes=evidence.get("notes"),
        )
        for evidence in entry.get("evidence", [])
    ]
    return result


def _classification_from_payload(payload: dict[str, Any]) -> BulkScreeningClassification:
    eligibility = ((payload.get("eligibility") or {}).get("status") or "").upper()
    if eligibility == "PASS":
        return BulkScreeningClassification.MEETS_CRITERIA
    if eligibility == "FAIL" and _has_verified_hard_gate_failure(payload):
        return BulkScreeningClassification.DOES_NOT_MEET_CRITERIA
    return BulkScreeningClassification.NEEDS_REVIEW


def _has_verified_hard_gate_failure(payload: dict[str, Any]) -> bool:
    eligibility = payload.get("eligibility") or {}
    failed_requirement_ids = {str(value) for value in eligibility.get("failed_requirements", [])}
    details = eligibility.get("requirement_details", [])
    verified_failure_statuses = {"not_met", "below_minimum", "contradicted", "failed"}
    if not details and failed_requirement_ids:
        return True
    for detail in details:
        if not isinstance(detail, dict):
            continue
        status = str(detail.get("status") or "").lower()
        requirement_id = str(detail.get("requirement_id") or detail.get("id") or "")
        if status in verified_failure_statuses and (
            not failed_requirement_ids or requirement_id in failed_requirement_ids
        ):
            return True
    return False


def _is_systemic_bulk_failure(failure_code: str | None) -> bool:
    return failure_code in {
        "INVALID_STRUCTURED_JD",
        "INVALID_RUBRIC",
        "ENGINE_SCHEMA_UNSUPPORTED",
        "RUBRIC_NOT_APPROVED",
        "ENGINE_CONFIGURATION_ERROR",
    }


def _is_retriable_bulk_failure(failure_code: str | None) -> bool:
    return _is_systemic_bulk_failure(failure_code) or failure_code in {
        "CHANDRA_UNAVAILABLE",
        "GEMMA_UNAVAILABLE",
        "ENGINE_TIMEOUT",
        "ENGINE_OUTPUT_MISSING",
        "ENGINE_OUTPUT_INVALID",
        "ENGINE_EXECUTION_FAILED",
    }


def _concise_reason(payload: dict[str, Any], classification: BulkScreeningClassification) -> str:
    evaluations = payload.get("criterion_evaluations", [])
    matched = []
    adjacent = []
    missing = []
    for entry in evaluations:
        component = entry.get("component_assessment") or {}
        matched.extend(_matched_terms(component))
        adjacent.extend(str(item) for item in component.get("supported_adjacent_components", []))
        adjacent.extend(str(item) for item in component.get("source_declared_adjacent_components", []))
        adjacent.extend(str(item) for item in component.get("inferred_adjacent_components", []))
        missing.extend(_unmatched_terms(component))
        missing.extend(str(item) for item in entry.get("missing_information", []))
    months = (payload.get("experience_summary") or {}).get("confirmed_months")
    if classification == BulkScreeningClassification.MEETS_CRITERIA:
        evidence = ", ".join(matched[:3]) or "required evidence"
        month_text = f", with {months} months of confirmed relevant experience" if months is not None else ""
        return f"Required evidence is present for {evidence}{month_text}."
    if classification == BulkScreeningClassification.DOES_NOT_MEET_CRITERIA:
        gap = ", ".join(_verified_hard_gate_descriptions(payload)[:2]) or "one or more mandatory requirements"
        return f"Verified hard-gate evidence indicates the candidate is below {gap}."
    if matched or adjacent:
        evidence = ", ".join((matched + adjacent)[:3])
        gap = ", ".join(missing[:2])
        suffix = (
            f" {gap} is not demonstrated in the resume and should be verified."
            if gap
            else " HR review is still required."
        )
        return f"Related evidence was found for {evidence}.{suffix}"
    if missing:
        return "Some required evidence is not demonstrated in the resume and should be verified by HR."
    warning = ", ".join(str(item) for item in payload.get("warnings", [])[:2])
    return warning or "Evidence is incomplete or ambiguous and requires HR review."


def _verified_hard_gate_descriptions(payload: dict[str, Any]) -> list[str]:
    eligibility = payload.get("eligibility") or {}
    failed_requirement_ids = {str(value) for value in eligibility.get("failed_requirements", [])}
    descriptions = []
    for detail in eligibility.get("requirement_details", []):
        if not isinstance(detail, dict):
            continue
        status = str(detail.get("status") or "").lower()
        requirement_id = str(detail.get("requirement_id") or detail.get("id") or "")
        if status not in {"not_met", "below_minimum", "contradicted", "failed"}:
            continue
        if failed_requirement_ids and requirement_id not in failed_requirement_ids:
            continue
        descriptions.append(str(detail.get("description") or detail.get("name") or requirement_id))
    return descriptions


def _candidate_name_from_payload(payload: dict[str, Any], structured_resume_path: Path | None = None) -> str | None:
    profile = payload.get("candidate_profile") or payload.get("candidate") or {}
    for key in ("full_name", "name", "candidate_name"):
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    scoring_safe = profile.get("scoring_safe_profile") if isinstance(profile, dict) else None
    if isinstance(scoring_safe, dict):
        value = scoring_safe.get("display_name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    if structured_resume_path is not None and structured_resume_path.is_file():
        try:
            structured_resume = json.loads(structured_resume_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            structured_resume = {}
        personal = structured_resume.get("personal_information") if isinstance(structured_resume, dict) else None
        if isinstance(personal, dict):
            for key in ("full_name", "name", "candidate_name"):
                value = personal.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def safe_bulk_failure_message(failure_code: str | None, failure_message: str | None) -> str | None:
    if not failure_message:
        return None
    if _looks_internal_diagnostic(failure_message):
        return _safe_failure_message(EngineProviderError(failure_code or "ENGINE_EXECUTION_FAILED", failure_message))
    return failure_message


def _looks_internal_diagnostic(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "traceback",
            "validationerror",
            "pydantic_core",
            "/home/",
            "/users/",
            ".py:",
            "subprocess.",
            "chandra_eval/",
        )
    )


def _validate_structured_jd_confirmation(
    structured_jd: dict[str, Any],
    criteria: list[dict[str, Any]],
    *,
    target_designation: str | None = None,
) -> None:
    warnings = [
        str(warning).lower()
        for key in ("warnings", "extraction_warnings")
        for warning in structured_jd.get(key, [])
    ]
    blocking_phrases = (
        "not linked to any scoring criterion",
        "unsupported generic",
        "preferred requirement marked mandatory",
    )
    for warning in warnings:
        if any(phrase in warning for phrase in blocking_phrases):
            raise InvalidTransition("Ad-hoc JD criteria contain unresolved grounding warnings")
    _validate_structured_jd_variants_for_engine(
        {**structured_jd, "scoring_rubric": criteria},
        target_designation=target_designation,
    )


def _refresh_batch_counts(batch: BulkScreeningBatch) -> None:
    items = list(batch.items)
    batch.total_files = len(items)
    batch.accepted_count = len(
        [
            item
            for item in items
            if item.status not in {BulkScreeningItemStatus.DUPLICATE, BulkScreeningItemStatus.UNSUPPORTED}
        ]
    )
    batch.duplicate_count = len([item for item in items if item.status == BulkScreeningItemStatus.DUPLICATE])
    batch.unsupported_count = len([item for item in items if item.status == BulkScreeningItemStatus.UNSUPPORTED])
    batch.completed_count = len([item for item in items if item.status == BulkScreeningItemStatus.COMPLETED])
    batch.failed_count = len([item for item in items if item.status == BulkScreeningItemStatus.FAILED])
    progressed_items = [
        item
        for item in items
        if item.status not in {BulkScreeningItemStatus.DUPLICATE, BulkScreeningItemStatus.UNSUPPORTED}
        and item.resume_document_id
    ]
    batch.progress_percent = (
        round(sum(_item_progress_percent(item) for item in progressed_items) / len(progressed_items))
        if progressed_items
        else 0
    )
    active = [BulkScreeningItemStatus.PENDING, BulkScreeningItemStatus.RUNNING]
    if batch.accepted_count and all(item.status not in active for item in items if item.resume_document_id):
        batch.completed_at = batch.completed_at or utcnow()
        batch.status = (
            BulkScreeningBatchStatus.FAILED
            if batch.failed_count == batch.accepted_count
            else BulkScreeningBatchStatus.COMPLETED
        )
        batch.progress_percent = 100


def _current_approved_rubric(job: Job) -> JobRubricVersion | None:
    rubric = job.rubrics[0] if job.rubrics else None
    if rubric is None or not rubric.current_version_id:
        return None
    current = next((entry for entry in rubric.versions if entry.id == rubric.current_version_id), None)
    if current is None or current.status != RubricVersionStatus.APPROVED:
        return None
    if current.approved_payload_sha256 and current.approved_payload_sha256 != rubric_payload_hash(current):
        raise InvalidTransition("Current approved rubric hash does not match its persisted payload")
    return current


def _structured_jd_for_batch(batch: BulkScreeningBatch) -> dict:
    return _structured_jd_variants_for_batch(batch)[0][1]


def _structured_jd_variants_for_batch(batch: BulkScreeningBatch) -> list[tuple[str | None, dict[str, Any]]]:
    if batch.source_type == BulkScreeningSourceType.EXISTING_JOB and batch.rubric_version:
        payload = batch.rubric_version.structured_jd_payload
    else:
        payload = {**(batch.ad_hoc_structured_jd or {}), "scoring_rubric": batch.criteria_snapshot or []}
    return _structured_jd_variants_for_payload(payload, target_designation=batch.target_designation)


def _structured_jd_variants_for_payload(
    payload: dict[str, Any],
    *,
    target_designation: str | None = None,
) -> list[tuple[str | None, dict[str, Any]]]:
    if target_designation:
        return [
            (
                target_designation,
                validate_structured_jd_for_engine(payload, target_designation=target_designation).canonical_payload,
            )
        ]
    options = designation_options_for_structured_jd(payload)
    if len(options) <= 1:
        return [(options[0] if options else None, validate_structured_jd_for_engine(payload).canonical_payload)]
    return [
        (designation, validate_structured_jd_for_engine(payload, target_designation=designation).canonical_payload)
        for designation in options
    ]


def _validate_structured_jd_variants_for_engine(
    payload: dict[str, Any],
    *,
    target_designation: str | None = None,
) -> None:
    _structured_jd_variants_for_payload(payload, target_designation=target_designation)


def _strongest_variant_result(results: list[BulkVariantEvaluation]) -> BulkVariantEvaluation:
    if not results:
        raise EngineProviderError("ENGINE_OUTPUT_MISSING", "Engine evaluation artifact was not created")
    rank = {
        BulkScreeningClassification.MEETS_CRITERIA: 3,
        BulkScreeningClassification.NEEDS_REVIEW: 2,
        BulkScreeningClassification.DOES_NOT_MEET_CRITERIA: 1,
    }
    return max(results, key=lambda result: rank[_classification_from_payload(result.result.payload)])


def _evaluate_bulk_provider(
    provider: BulkScreeningProvider,
    item: BulkScreeningItem,
    *,
    progress: ProgressCallback,
) -> ProviderExecutionResult:
    try:
        return provider.evaluate(item, progress=progress)
    except TypeError as error:
        if "progress" not in str(error):
            raise
        return provider.evaluate(item)  # type: ignore[call-arg]


def _set_bulk_processing_stage(
    db: Session,
    job: BulkScreeningWorkItem,
    stage: str,
    *,
    commit: bool,
) -> None:
    now = utcnow()
    progress = BULK_PROCESSING_STAGE_PROGRESS.get(stage, job.progress_percent)
    item = job.item
    batch = item.batch
    job.processing_stage = stage
    job.progress_percent = progress
    job.stage_updated_at = now
    item.processing_stage = stage
    item.progress_percent = progress
    item.stage_updated_at = now
    if stage == "COMPLETED":
        item.status = BulkScreeningItemStatus.COMPLETED
        job.status = BulkScreeningItemStatus.COMPLETED
    else:
        item.status = BulkScreeningItemStatus.RUNNING
        job.status = BulkScreeningItemStatus.RUNNING
        batch.status = BulkScreeningBatchStatus.RUNNING
    _refresh_batch_counts(batch)
    db.flush()
    if commit:
        db.commit()


def _item_progress_percent(item: BulkScreeningItem) -> int:
    if item.status in {BulkScreeningItemStatus.COMPLETED, BulkScreeningItemStatus.FAILED}:
        return 100
    return max(0, min(100, int(item.progress_percent or 0)))


def _designation_artifact_suffix(designation: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in designation.lower()).strip("-") or "designation"


def _generate_ad_hoc_structured_jd(document: Document) -> dict[str, Any]:
    if get_settings().screening_provider == "engine":
        return _generate_engine_ad_hoc_structured_jd(document)
    return _generate_mock_ad_hoc_structured_jd(document)


def _generate_engine_ad_hoc_structured_jd(document: Document) -> dict[str, Any]:
    settings = get_settings()
    engine_root = Path(settings.screening_engine_root).expanduser().resolve()
    if not engine_root.is_dir():
        raise EngineProviderError("ENGINE_CONFIGURATION_ERROR", "Screening engine root does not exist")
    output_root = Path(settings.screening_output_root).expanduser().resolve()
    run_dir = output_root / "bulk-jd" / document.id
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "structured-jd.json"
    jd_path = LocalDocumentStorage().resolve_path(document)
    _run_command(
        _engine_command(
            settings,
            engine_root / "scripts" / "extract_jd.py",
            str(jd_path),
            "--job-id",
            f"bulk-{document.id}",
            "--output",
            str(output_path),
        ),
        cwd=engine_root,
        timeout=settings.screening_engine_timeout_seconds,
        env=_engine_environment(settings, gemma_base_url=settings.screening_gemma_base_url),
        failure_code="ENGINE_EXECUTION_FAILED",
    )
    return json.loads(output_path.read_text(encoding="utf-8"))


def _generate_mock_ad_hoc_structured_jd(document: Document) -> dict[str, Any]:
    text = LocalDocumentStorage().resolve_path(document).read_bytes()[:5000].decode("utf-8", errors="ignore")
    title = Path(document.original_filename).stem.replace("_", " ").replace("-", " ").title() or "Ad-hoc bulk role"
    skills = _extract_mock_skills(text)
    criteria = [
        {
            "criterion_id": "required_skills",
            "name": "Required skills evidence",
            "category": "skill",
            "weight": 45,
            "mandatory": True,
            "required_skill_names": skills[:4],
            "preferred_skill_names": skills[4:8],
            "adjacent_skill_names": [],
            "evaluation_dimensions": ["role-relevant evidence"],
            "requirement_ids": [f"required-skill-{index}" for index, _skill in enumerate(skills[:4], start=1)],
        },
        {
            "criterion_id": "experience",
            "name": "Relevant experience",
            "category": "experience",
            "weight": 35,
            "mandatory": True,
            "required_skill_names": [],
            "preferred_skill_names": [],
            "adjacent_skill_names": [],
            "evaluation_dimensions": ["confirmed months"],
        },
        {
            "criterion_id": "delivery",
            "name": "Delivery and collaboration",
            "category": "skill",
            "weight": 20,
            "mandatory": False,
            "required_skill_names": [],
            "preferred_skill_names": ["Git", "Documentation", "Communication"],
            "adjacent_skill_names": [],
            "evaluation_dimensions": ["collaboration"],
        },
    ]
    return {
        "schema_version": "structured-jd-v1",
        "job_id": f"bulk-{document.id}",
        "source_document_id": document.id,
        "extraction_method": "mock_gemma",
        "job_title": title,
        "department": "Ad-hoc bulk screening",
        "role_summary": text[:500] or "Ad-hoc JD uploaded for bulk screening.",
        "responsibilities": [],
        "mandatory_requirements": [
            {
                "requirement_id": f"required-skill-{index}",
                "category": "skill",
                "description": f"Evidence for {skill}",
                "requirement_type": "minimum",
                "mandatory": True,
                "preferred": False,
                "minimum_value": None,
                "unit": None,
                "accepted_equivalents": [],
                "evidence": [],
                "warnings": [],
            }
            for index, skill in enumerate(skills[:4], start=1)
        ],
        "preferred_requirements": [
            {
                "requirement_id": f"preferred-skill-{index}",
                "category": "skill",
                "description": f"Evidence for {skill}",
                "requirement_type": "preferred",
                "mandatory": False,
                "preferred": True,
                "minimum_value": None,
                "unit": None,
                "accepted_equivalents": [],
                "evidence": [],
                "warnings": [],
            }
            for index, skill in enumerate(skills[4:8], start=1)
        ],
        "required_skills": skills[:4],
        "preferred_skills": skills[4:8],
        "minimum_experience_months": 0,
        "domain": "Ad-hoc bulk screening",
        "seniority": "",
        "scoring_rubric": criteria,
        "extraction_warnings": ["Mock ad-hoc JD extraction for local development."],
    }


def _extract_mock_skills(text: str) -> list[str]:
    known = ["React", "Node.js", "SQL", "Laravel", "PHP", "WordPress", "Python", "Writing", "SEO", "Editing"]
    lowered = text.lower()
    found = [skill for skill in known if skill.lower() in lowered]
    return found or ["Role-relevant skill", "Communication", "Problem solving", "Experience"]


def _bulk_provider_from_settings() -> BulkScreeningProvider:
    if get_settings().screening_provider == "engine":
        return HiringScreeningEngineBulkProvider()
    return MockBulkScreeningProvider()


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
    for key in ("missing_core_components", "missing_preferred_components", "missing_evaluation_dimensions"):
        terms.extend(str(item) for item in component_assessment.get(key, []))
    return sorted(set(terms))


def _content_type_for(filename: str, fallback: str) -> str:
    guessed = mimetypes.guess_type(filename)[0]
    if guessed:
        return guessed
    return fallback or "application/octet-stream"


def _display_filename(filename: str) -> str:
    name = Path(filename).name
    if not name or name in {".", ".."}:
        raise DomainError("Uploaded file requires a safe filename")
    return name


def _hash_json(payload: dict[str, Any]) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
