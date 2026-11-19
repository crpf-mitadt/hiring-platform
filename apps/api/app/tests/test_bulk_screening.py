import io
import json
import threading
import zipfile
from pathlib import Path

from app.models import BulkScreeningBatch, BulkScreeningItem, BulkScreeningWorkItem, Job, JobRubricVersion
from app.services.bulk_screening import (
    BulkVariantEvaluation,
    _strongest_variant_result,
    process_next_bulk_screening_jobs,
)
from app.services.rubric_utils import rubric_payload_hash
from app.services.screening import ProviderExecutionResult
from app.services.structured_jd_contract import validate_structured_jd_for_engine
from app.worker import run_pending_screening_jobs
from pypdf import PdfWriter
from sqlalchemy import select


def _pdf_bytes(text: bytes | str = b"meets all required evidence", *, pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _index in range(pages):
        writer.add_blank_page(width=612, height=792)
    body = text.decode("utf-8", errors="ignore") if isinstance(text, bytes) else text
    writer.add_metadata({"/Subject": body})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _encrypted_pdf_bytes(*, pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _index in range(pages):
        writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _resume_file(filename: str, content: bytes | str | None = None, *, pages: int = 1):
    return ("files", (filename, _pdf_bytes(content or b"meets all required evidence", pages=pages), "application/pdf"))


def _zip_file(entries: dict[str, bytes], filename: str = "resumes.zip"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    buffer.seek(0)
    return ("zip_file", (filename, buffer.read(), "application/zip"))


def _create_existing_batch(client, actor_id: str, job_id: str, files=None):
    return client.post(
        "/api/bulk-screening/batches/existing-job",
        headers={"X-Actor-Id": actor_id},
        data={"job_id": job_id},
        files=files or [],
    )


def _create_simple_batch(client, actor_id: str, jd_content: bytes, files, target_designation: str | None = None):
    data = {}
    if target_designation:
        data["target_designation"] = target_designation
    return client.post(
        "/api/bulk-screening/simple",
        headers={"X-Actor-Id": actor_id},
        data=data,
        files=[("jd_file", ("faculty-jd.txt", jd_content, "text/plain")), *files],
    )


def _upload_resumes(client, actor_id: str, batch_id: str, files):
    return client.post(
        f"/api/bulk-screening/batches/{batch_id}/resumes",
        headers={"X-Actor-Id": actor_id},
        files=files,
    )


def _start_batch(client, actor_id: str, batch_id: str):
    return client.post(
        f"/api/bulk-screening/batches/{batch_id}/start",
        headers={"X-Actor-Id": actor_id},
    )


def _assert_no_score_keys(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert "score" not in key.lower()
            assert key not in {"final_score", "weighted_score", "score_before_gates", "maximum_score"}
            _assert_no_score_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_score_keys(item)


def _multi_designation_structured_jd():
    return {
        "schema_version": "structured-jd-v1",
        "job_id": "multi-rank",
        "source_document_id": "jd",
        "extraction_method": "live_gemma",
        "job_title": "Assistant Professor, Associate Professor & Professor",
        "department": "Faculty",
        "role_summary": "Faculty appointment across designation-specific tracks.",
        "mandatory_requirements": [
            {
                "requirement_id": "req_002",
                "category": "experience",
                "description": "minimum 2 years (Assistant Professor)",
                "requirement_type": "minimum",
                "mandatory": True,
                "preferred": False,
                "minimum_value": 2,
                "unit": "years",
            },
            {
                "requirement_id": "req_003",
                "category": "experience",
                "description": "minimum 8 years (Associate Professor)",
                "requirement_type": "minimum",
                "mandatory": True,
                "preferred": False,
                "minimum_value": 8,
                "unit": "years",
            },
            {
                "requirement_id": "req_004",
                "category": "experience",
                "description": "minimum 10 years (Professor)",
                "requirement_type": "minimum",
                "mandatory": True,
                "preferred": False,
                "minimum_value": 10,
                "unit": "years",
            },
            {
                "requirement_id": "req_007",
                "category": "research",
                "description": "2+ papers in Scopus/WoS (Assistant Professor)",
                "requirement_type": "minimum",
                "mandatory": True,
                "preferred": False,
            },
        ],
        "preferred_requirements": [],
        "required_skills": ["Teaching", "Research"],
        "preferred_skills": [],
        "minimum_experience_months": 0,
        "domain": "Faculty",
        "seniority": "",
        "scoring_rubric": [
            {
                "criterion_id": "crit_002",
                "name": "Relevant Experience",
                "category": "experience",
                "description": "Designation-scoped experience threshold",
                "weight": 60,
                "mandatory": True,
                "requirement_ids": ["req_002", "req_003", "req_004"],
            },
            {
                "criterion_id": "crit_004",
                "name": "Research & Innovation",
                "category": "research",
                "description": "Designation-scoped research output",
                "weight": 40,
                "mandatory": True,
                "requirement_ids": ["req_007"],
            },
        ],
    }


def test_bulk_screening_denies_candidate_and_anonymous(client, users, published_job):
    anonymous = client.get("/api/bulk-screening/batches")
    assert anonymous.status_code == 401

    candidate = _create_existing_batch(
        client,
        users["candidate"]["id"],
        published_job["id"],
    )
    assert candidate.status_code == 403


def test_bulk_screening_creates_existing_job_batch_before_review(
    client,
    db_session,
    users,
    published_job,
):
    response = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_type"] == "EXISTING_JOB"
    assert body["status"] == "READY"
    assert body["accepted_count"] == 0
    assert body["completed_count"] == 0
    assert body["items"] == []
    assert db_session.scalar(select(BulkScreeningWorkItem)) is None
    _assert_no_score_keys(body)


def test_bulk_screening_uploads_before_review_and_start_enqueues_persisted_items(
    client,
    db_session,
    users,
    published_job,
):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    assert created.status_code == 200, created.text
    batch_id = created.json()["id"]

    uploaded = _upload_resumes(
        client,
        users["recruiter"]["id"],
        batch_id,
        [_resume_file("first.pdf"), _resume_file("second.pdf", b"%PDF-1.4 missing mandatory Laravel")],
    )

    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["status"] == "READY"
    assert body["total_files"] == 2
    assert body["accepted_count"] == 2
    assert [item["original_filename"] for item in body["items"]] == ["first.pdf", "second.pdf"]
    assert all(item["status"] == "PENDING" for item in body["items"])
    assert all(item["provider"] is None for item in body["items"])
    assert db_session.scalar(select(BulkScreeningWorkItem)) is None

    started = _start_batch(client, users["recruiter"]["id"], batch_id)

    assert started.status_code == 200, started.text
    assert started.json()["status"] == "QUEUED"
    assert len(list(db_session.scalars(select(BulkScreeningWorkItem)))) == 2


def test_bulk_screening_requires_current_approved_rubric(client, users, draft_job):
    rubric = client.post(
        f"/api/jobs/{draft_job['id']}/generate-rubric",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert rubric.status_code == 200

    response = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        draft_job["id"],
    )

    assert response.status_code == 409


def test_bulk_screening_ad_hoc_jd_requires_confirmation_before_resumes(client, users):
    jd = client.post(
        "/api/bulk-screening/batches/ad-hoc-jd",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        files={"jd_file": ("full-stack-jd.txt", b"React Node.js SQL Laravel 24 months", "text/plain")},
    )
    assert jd.status_code == 200, jd.text
    batch_id = jd.json()["id"]
    assert jd.json()["status"] == "DRAFT"
    assert jd.json()["criteria_snapshot"]

    blocked = client.post(
        f"/api/bulk-screening/batches/{batch_id}/resumes",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        files=[_resume_file("candidate.pdf")],
    )
    assert blocked.status_code == 409

    confirmed = client.post(
        f"/api/bulk-screening/batches/{batch_id}/confirm-criteria",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"confirmed": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "READY"

    uploaded = _upload_resumes(client, users["recruiter"]["id"], batch_id, [_resume_file("candidate.pdf")])
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["status"] == "READY"

    started = _start_batch(client, users["recruiter"]["id"], batch_id)
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "QUEUED"


def test_simple_bulk_screening_creates_ad_hoc_batch_and_queues_one_resume(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [_resume_file("candidate.pdf")],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_type"] == "ADHOC_JD"
    assert body["status"] == "QUEUED"
    assert body["criteria_confirmed_at"] is not None
    assert body["accepted_count"] == 1
    assert body["items"][0]["original_filename"] == "candidate.pdf"
    assert len(list(db_session.scalars(select(BulkScreeningWorkItem)))) == 1


def test_simple_bulk_screening_handles_multiple_resumes_and_dedupe(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [
            _resume_file("first.pdf", b"%PDF-1.4 same resume"),
            _resume_file("first-copy.pdf", b"%PDF-1.4 same resume"),
            _resume_file("second.pdf", b"%PDF-1.4 different resume"),
        ],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["total_files"] == 3
    assert body["accepted_count"] == 2
    assert body["duplicate_count"] == 1
    assert [item["status"] for item in body["items"]].count("DUPLICATE") == 1
    assert len(list(db_session.scalars(select(BulkScreeningWorkItem)))) == 2


def test_simple_bulk_screening_accepts_one_page_pdf_resume(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [_resume_file("one-page.pdf", pages=1)],
    )

    assert response.status_code == 200, response.text
    assert response.json()["accepted_count"] == 1
    assert response.json()["items"][0]["status"] == "PENDING"
    assert len(list(db_session.scalars(select(BulkScreeningWorkItem)))) == 1


def test_simple_bulk_screening_accepts_four_page_pdf_resume(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [_resume_file("four-page.pdf", pages=4)],
    )

    assert response.status_code == 200, response.text
    assert response.json()["accepted_count"] == 1
    assert response.json()["items"][0]["status"] == "PENDING"
    assert len(list(db_session.scalars(select(BulkScreeningWorkItem)))) == 1


def test_simple_bulk_screening_pdf_text_markers_do_not_change_parser_page_count(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [_resume_file("marker-text.pdf", "resume text mentions /Type /Page /Type /Page", pages=1)],
    )

    assert response.status_code == 200, response.text
    assert response.json()["accepted_count"] == 1
    assert response.json()["items"][0]["status"] == "PENDING"
    assert len(list(db_session.scalars(select(BulkScreeningWorkItem)))) == 1


def test_simple_bulk_screening_rejects_five_page_resume_before_queueing(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [_resume_file("five-page.pdf", pages=5)],
    )

    assert response.status_code == 409
    assert response.json()["code"] == "NO_SCREENABLE_RESUMES"
    assert response.json()["issues"][0]["type"] == "RESUME_TOO_LONG"
    assert response.json()["issues"][0]["original_filename"] == "five-page.pdf"
    assert "5 pages" in response.json()["issues"][0]["description"]
    assert db_session.scalar(select(BulkScreeningWorkItem)) is None
    assert db_session.scalar(select(BulkScreeningBatch)) is None


def test_simple_bulk_screening_mixed_valid_and_oversized_resumes_queues_only_valid(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [
            _resume_file("valid-a.pdf", pages=2),
            _resume_file("oversized.pdf", pages=6),
            _resume_file("valid-b.pdf", pages=4),
        ],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["accepted_count"] == 2
    assert body["unsupported_count"] == 1
    by_file = {item["original_filename"]: item for item in body["items"]}
    assert by_file["oversized.pdf"]["status"] == "UNSUPPORTED"
    assert by_file["oversized.pdf"]["failure_code"] == "RESUME_TOO_LONG"
    assert by_file["valid-a.pdf"]["status"] == "PENDING"
    assert by_file["valid-b.pdf"]["status"] == "PENDING"
    work_items = list(db_session.scalars(select(BulkScreeningWorkItem)))
    assert len(work_items) == 2
    assert {item.item.original_filename for item in work_items} == {"valid-a.pdf", "valid-b.pdf"}

    seen_by_provider: list[str] = []

    class RecordingProvider:
        name = "recording-provider"
        engine_version = "test"

        def evaluate(self, item, progress=None):
            seen_by_provider.append(item.original_filename)
            if progress:
                progress("COMPARING_WITH_JD")
            return ProviderExecutionResult(
                provider=self.name,
                provider_engine_version=self.engine_version,
                payload={
                    "artifact_schema_version": "candidate-evaluation-v1",
                    "eligibility": {"status": "PASS"},
                    "criterion_evaluations": [],
                    "evidence_completeness": 1,
                    "experience_summary": {"confirmed_months": 24},
                },
            )

    while process_next_bulk_screening_jobs(db_session, provider=RecordingProvider()):
        db_session.commit()

    assert seen_by_provider == ["valid-a.pdf", "valid-b.pdf"]
    assert "oversized.pdf" not in seen_by_provider


def test_simple_bulk_screening_invalid_pdf_is_reported_safely_before_queueing(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [("files", ("invalid.pdf", b"not a pdf", "application/pdf"))],
    )

    assert response.status_code == 409
    assert response.json()["code"] == "NO_SCREENABLE_RESUMES"
    assert response.json()["issues"][0]["type"] == "INVALID_PDF"
    assert response.json()["issues"][0]["original_filename"] == "invalid.pdf"
    assert db_session.scalar(select(BulkScreeningWorkItem)) is None
    assert db_session.scalar(select(BulkScreeningBatch)) is None


def test_simple_bulk_screening_encrypted_pdf_is_reported_safely_before_queueing(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [("files", ("encrypted.pdf", _encrypted_pdf_bytes(), "application/pdf"))],
    )

    assert response.status_code == 409
    assert response.json()["code"] == "NO_SCREENABLE_RESUMES"
    assert response.json()["issues"][0]["type"] == "INVALID_PDF"
    assert response.json()["issues"][0]["original_filename"] == "encrypted.pdf"
    assert db_session.scalar(select(BulkScreeningWorkItem)) is None
    assert db_session.scalar(select(BulkScreeningBatch)) is None


def test_simple_bulk_screening_reconciles_deterministic_mandatory_criteria(client, monkeypatch, users):
    monkeypatch.setattr(
        "app.services.bulk_screening._generate_ad_hoc_structured_jd",
        lambda _document: {
            "schema_version": "structured-jd-v1",
            "job_id": "adhoc",
            "source_document_id": "jd",
            "extraction_method": "live_gemma",
            "job_title": "Assistant Professor",
            "department": "Faculty",
            "mandatory_requirements": [
                {
                    "requirement_id": "req_007",
                    "category": "research",
                    "description": "2+ papers in Scopus/WoS",
                    "requirement_type": "minimum",
                    "mandatory": True,
                    "preferred": False,
                }
            ],
            "preferred_requirements": [],
            "scoring_rubric": [
                {
                    "criterion_id": "crit_004",
                    "name": "Research & Innovation",
                    "category": "research",
                    "description": "Research output",
                    "weight": 100,
                    "mandatory": False,
                    "requirement_ids": ["req_007"],
                }
            ],
        },
    )

    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"research JD",
        [_resume_file("candidate.pdf")],
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "QUEUED"
    assert response.json()["criteria_snapshot"][0]["mandatory"] is True


def test_simple_bulk_screening_accepts_multi_rank_jd_without_designation_selector(client, monkeypatch, users):
    monkeypatch.setattr(
        "app.services.bulk_screening._generate_ad_hoc_structured_jd",
        lambda _document: _multi_designation_structured_jd(),
    )

    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"assistant associate professor",
        [_resume_file("candidate.pdf")],
    )

    assert response.status_code == 200, response.text
    assert response.json()["target_designation"] is None
    assert response.json()["status"] == "QUEUED"
    assert response.json()["progress_percent"] == 0
    assert response.json()["items"][0]["processing_stage"] == "QUEUED"


def test_simple_bulk_screening_ignores_stale_multi_rank_grounding_warning(client, monkeypatch, users):
    payload = _multi_designation_structured_jd()
    payload["extraction_warnings"] = ["mandatory requirement was not linked to any scoring criterion"]
    monkeypatch.setattr("app.services.bulk_screening._generate_ad_hoc_structured_jd", lambda _document: payload)

    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"assistant associate professor",
        [_resume_file("candidate.pdf")],
    )

    assert response.status_code == 200, response.text
    assert response.json()["target_designation"] is None
    assert response.json()["status"] == "QUEUED"


def test_simple_bulk_screening_invalid_jd_preflight_prevents_resume_queueing(client, db_session, monkeypatch, users):
    monkeypatch.setattr(
        "app.services.bulk_screening._generate_ad_hoc_structured_jd",
        lambda _document: {
            "schema_version": "structured-jd-v1",
            "job_id": "adhoc",
            "source_document_id": "jd",
            "extraction_method": "live_gemma",
            "job_title": "Invalid JD",
            "department": "Faculty",
            "mandatory_requirements": ["not canonical"],
            "scoring_rubric": [{"criterion_id": "bad", "name": "Bad", "category": "invalid", "weight": 100}],
        },
    )

    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"invalid JD",
        [_resume_file("candidate.pdf")],
    )

    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_SCREENING_CRITERIA"
    assert db_session.scalar(select(BulkScreeningWorkItem)) is None


def test_simple_bulk_screening_processes_mock_results_into_final_classifications(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [
            _resume_file("meets.pdf", b"%PDF-1.4 meets all required evidence"),
            _resume_file("missing.pdf", b"%PDF-1.4 missing mandatory evidence"),
            _resume_file("review.pdf", b"%PDF-1.4 ambiguous review evidence"),
            _resume_file("technical.pdf", b"%PDF-1.4 provider failure"),
        ],
    )
    assert response.status_code == 200, response.text
    batch_id = response.json()["id"]

    while process_next_bulk_screening_jobs(db_session):
        db_session.commit()

    refreshed = client.get(
        f"/api/bulk-screening/batches/{batch_id}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )

    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["status"] == "COMPLETED"
    classifications = {item["original_filename"]: item["classification"] for item in body["items"]}
    assert classifications["meets.pdf"] == "MEETS_CRITERIA"
    assert classifications["missing.pdf"] == "DOES_NOT_MEET_CRITERIA"
    assert classifications["review.pdf"] == "NEEDS_REVIEW"
    assert classifications["technical.pdf"] == "NEEDS_REVIEW"
    technical = next(item for item in body["items"] if item["original_filename"] == "technical.pdf")
    assert technical["status"] == "FAILED"
    assert "technical processing failure" in technical["concise_reason"]
    assert "/home/" not in (technical["failure_message"] or "")
    assert "Traceback" not in (technical["failure_message"] or "")


def test_bulk_screening_commits_running_stage_before_provider_finishes(client, db_session, users):
    response = _create_simple_batch(
        client,
        users["recruiter"]["id"],
        b"React Node.js SQL Laravel 24 months",
        [_resume_file("candidate.pdf", b"%PDF-1.4 meets all required evidence")],
    )
    assert response.status_code == 200, response.text
    batch_id = response.json()["id"]

    class InspectingProvider:
        name = "inspecting-provider"
        engine_version = "test"

        def evaluate(self, item, progress=None):
            if progress:
                progress("STRUCTURING_PROFILE")
            visible = client.get(
                f"/api/bulk-screening/batches/{batch_id}",
                headers={"X-Actor-Id": users["recruiter"]["id"]},
            )
            assert visible.status_code == 200, visible.text
            body = visible.json()
            assert body["status"] == "RUNNING"
            assert body["progress_percent"] > 0
            assert body["items"][0]["status"] == "RUNNING"
            assert body["items"][0]["processing_stage"] == "STRUCTURING_PROFILE"
            assert body["items"][0]["progress_percent"] == 45
            if progress:
                progress("COMPARING_WITH_JD")
            return ProviderExecutionResult(
                provider=self.name,
                provider_engine_version=self.engine_version,
                payload={
                    "artifact_schema_version": "candidate-evaluation-v1",
                    "eligibility": {"status": "PASS"},
                    "criterion_evaluations": [],
                    "evidence_completeness": 1,
                    "experience_summary": {"confirmed_months": 24},
                },
            )

    assert process_next_bulk_screening_jobs(db_session, provider=InspectingProvider()) == 1
    db_session.commit()
    completed = client.get(
        f"/api/bulk-screening/batches/{batch_id}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    ).json()
    assert completed["status"] == "COMPLETED"
    assert completed["progress_percent"] == 100
    assert completed["items"][0]["processing_stage"] == "COMPLETED"


def test_bulk_screening_handles_duplicates_and_unsupported_files_before_review(
    client,
    db_session,
    users,
    published_job,
):
    same = b"%PDF-1.4 meets all required evidence"
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    response = _upload_resumes(
        client,
        users["recruiter"]["id"],
        created.json()["id"],
        [
            _resume_file("first.pdf", same),
            _resume_file("duplicate.pdf", same),
            ("files", ("notes.txt", b"plain text resume", "text/plain")),
        ],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["duplicate_count"] == 1
    assert body["unsupported_count"] == 1
    assert {item["status"] for item in body["items"]} == {"PENDING", "DUPLICATE", "UNSUPPORTED"}
    assert db_session.scalar(select(BulkScreeningWorkItem)) is None

    started = _start_batch(client, users["recruiter"]["id"], created.json()["id"])
    assert started.status_code == 200, started.text
    assert len(list(db_session.scalars(select(BulkScreeningWorkItem)))) == 1


def test_bulk_screening_zip_security_rejects_path_traversal_and_nested_zip(client, users, published_job):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    traversal = _upload_resumes(
        client,
        users["recruiter"]["id"],
        created.json()["id"],
        [_zip_file({"../escape.pdf": b"%PDF-1.4"})],
    )
    assert traversal.status_code == 400

    nested = _upload_resumes(
        client,
        users["recruiter"]["id"],
        created.json()["id"],
        [_zip_file({"nested.zip": b"PK fake"})],
    )
    assert nested.status_code == 400


def test_bulk_screening_zip_security_rejects_oversized_archive(client, users, published_job):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    response = _upload_resumes(
        client,
        users["recruiter"]["id"],
        created.json()["id"],
        [_zip_file({"large.pdf": b"x" * (51 * 1024 * 1024)})],
    )
    assert response.status_code == 400


def test_bulk_screening_processes_pass_fail_review_and_technical_failure(
    client,
    db_session,
    users,
    published_job,
):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    response = _upload_resumes(
        client,
        users["recruiter"]["id"],
        created.json()["id"],
        [
            _resume_file("meets.pdf", b"%PDF-1.4 meets all required evidence"),
            _resume_file("missing.pdf", b"%PDF-1.4 missing mandatory evidence"),
            _resume_file("review.pdf", b"%PDF-1.4 ambiguous review evidence"),
            _resume_file("technical.pdf", b"%PDF-1.4 provider failure"),
        ],
    )
    assert response.status_code == 200, response.text
    batch_id = response.json()["id"]
    started = _start_batch(client, users["recruiter"]["id"], batch_id)
    assert started.status_code == 200, started.text

    while process_next_bulk_screening_jobs(db_session):
        db_session.commit()

    refreshed = client.get(
        f"/api/bulk-screening/batches/{batch_id}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    by_file = {item["original_filename"]: item for item in body["items"]}
    assert by_file["meets.pdf"]["classification"] == "MEETS_CRITERIA"
    assert by_file["missing.pdf"]["classification"] == "DOES_NOT_MEET_CRITERIA"
    assert "hard-gate" in by_file["missing.pdf"]["concise_reason"].lower()
    assert by_file["review.pdf"]["classification"] == "NEEDS_REVIEW"
    assert by_file["technical.pdf"]["classification"] == "NEEDS_REVIEW"
    assert by_file["technical.pdf"]["status"] == "FAILED"
    assert by_file["technical.pdf"]["failure_code"] == "ENGINE_EXECUTION_FAILED"
    assert by_file["technical.pdf"]["concise_reason"]
    _assert_no_score_keys(body)
    assert "final_score" not in json.dumps(body)


def test_bulk_screening_export_is_score_free(client, db_session, users, published_job):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    response = _upload_resumes(
        client,
        users["recruiter"]["id"],
        created.json()["id"],
        [_resume_file("meets.pdf", b"%PDF-1.4 meets all required evidence")],
    )
    assert response.status_code == 200, response.text
    batch_id = response.json()["id"]
    started = _start_batch(client, users["recruiter"]["id"], batch_id)
    assert started.status_code == 200, started.text

    while process_next_bulk_screening_jobs(db_session):
        db_session.commit()

    export = client.get(
        f"/api/bulk-screening/batches/{batch_id}/export.csv",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )

    assert export.status_code == 200
    assert "filename,candidate_name,classification,status" in export.text
    assert "MEETS_CRITERIA" in export.text
    assert "eligibility" not in export.text.lower()
    assert "evidence_completeness" not in export.text.lower()
    assert "confirmed_experience_months" not in export.text.lower()
    assert "score" not in export.text.lower()
    assert "rank" not in export.text.lower()


def test_bulk_screening_worker_consumes_bulk_queue_with_existing_loop(
    client,
    db_session,
    monkeypatch,
    users,
    published_job,
):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    response = _upload_resumes(
        client,
        users["recruiter"]["id"],
        created.json()["id"],
        [_resume_file("meets.pdf")],
    )
    assert response.status_code == 200, response.text
    started = _start_batch(client, users["recruiter"]["id"], response.json()["id"])
    assert started.status_code == 200, started.text

    class TestSessionLocal:
        def __enter__(self):
            return db_session

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr("app.worker.SessionLocal", lambda: TestSessionLocal())
    processed = run_pending_screening_jobs(
        poll_interval_seconds=0.001,
        max_poll_interval_seconds=0.001,
        max_idle_cycles=1,
        stop_event=threading.Event(),
    )

    assert processed == 1
    item = db_session.scalar(select(BulkScreeningItem))
    assert item.status.value == "COMPLETED"
    assert item.classification.value == "MEETS_CRITERIA"


def test_bulk_screening_filename_pii_does_not_drive_classification(client, db_session, users, published_job):
    content = b"%PDF-1.4 meets all required evidence"
    first_created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    first = _upload_resumes(
        client,
        users["recruiter"]["id"],
        first_created.json()["id"],
        [_resume_file("Aarav_PrivatePhone9999999999.pdf", content)],
    )
    second_created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    second = _upload_resumes(
        client,
        users["recruiter"]["id"],
        second_created.json()["id"],
        [_resume_file("Different_Name_DOB_1990.pdf", content)],
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert _start_batch(client, users["recruiter"]["id"], first.json()["id"]).status_code == 200
    assert _start_batch(client, users["recruiter"]["id"], second.json()["id"]).status_code == 200

    while process_next_bulk_screening_jobs(db_session):
        db_session.commit()

    items = list(db_session.scalars(select(BulkScreeningItem).order_by(BulkScreeningItem.created_at)))
    assert items[0].classification == items[1].classification


def test_bulk_screening_format_contract(client):
    response = client.get("/api/bulk-screening/formats")
    assert response.status_code == 200
    assert response.json()["jd"] == [".docx", ".md", ".pdf", ".txt"]
    assert response.json()["resumes"] == [".pdf"]
    assert "Structured JSON resumes remain an integration/test capability" in " ".join(response.json()["notes"])
    assert ".doc" in response.json()["unsupported"]
    assert ".heic" in response.json()["unsupported"]


def test_bulk_screening_completed_batch_cannot_restart_or_discard(client, db_session, users, published_job):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(client, users["recruiter"]["id"], created.json()["id"], [_resume_file("meets.pdf")])
    started = _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"])
    assert started.status_code == 200, started.text

    while process_next_bulk_screening_jobs(db_session):
        db_session.commit()

    restart = _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"])
    discard = client.delete(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )

    assert restart.status_code == 409
    assert discard.status_code == 409


def test_bulk_screening_discards_unstarted_draft(client, users, published_job):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(client, users["recruiter"]["id"], created.json()["id"], [_resume_file("candidate.pdf")])
    assert uploaded.status_code == 200, uploaded.text

    discard = client.delete(
        f"/api/bulk-screening/batches/{created.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    reopened = client.get(
        f"/api/bulk-screening/batches/{created.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )

    assert discard.status_code == 204
    assert reopened.status_code == 404


def test_bulk_screening_archives_terminal_batch_and_excludes_default_history(client, db_session, users, published_job):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(client, users["recruiter"]["id"], created.json()["id"], [_resume_file("meets.pdf")])
    assert _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"]).status_code == 200

    while process_next_bulk_screening_jobs(db_session):
        db_session.commit()

    archive = client.post(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}/archive",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    history = client.get("/api/bulk-screening/batches", headers={"X-Actor-Id": users["recruiter"]["id"]})
    direct = client.get(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )

    assert archive.status_code == 200, archive.text
    assert archive.json()["archived_at"] is not None
    assert archive.json()["archived_by_id"] == users["recruiter"]["id"]
    assert uploaded.json()["id"] not in {batch["id"] for batch in history.json()}
    assert direct.status_code == 200
    assert direct.json()["archived_at"] is not None


def test_bulk_screening_rejects_active_archive_and_delete(client, users, published_job):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(client, users["recruiter"]["id"], created.json()["id"], [_resume_file("meets.pdf")])
    started = _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"])
    assert started.status_code == 200

    archive = client.post(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}/archive",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    discard = client.delete(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )

    assert archive.status_code == 409
    assert discard.status_code == 409


def test_bulk_screening_existing_job_preflight_blocks_invalid_structured_jd(client, users, published_job, db_session):
    job = db_session.get(Job, published_job["id"])
    version = db_session.get(JobRubricVersion, job.rubrics[0].current_version_id)
    version.structured_jd_payload = {
        "schema_version": "structured-jd-v1",
        "job_id": job.id,
        "source_document_id": job.jd_document_id or "jd",
        "extraction_method": "development_manual_seed",
        "job_title": job.title,
        "department": job.department.name,
        "mandatory_requirements": ["not canonical"],
        "scoring_rubric": [{"criterion_id": "bad", "name": "Bad", "category": "invalid_category", "weight": 100}],
        "seed_revision": "legacy",
    }
    version.criteria = version.structured_jd_payload["scoring_rubric"]
    version.approved_payload_sha256 = rubric_payload_hash(version)
    db_session.commit()

    response = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])

    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_SCREENING_CRITERIA"
    assert response.json()["issues"]


def test_bulk_screening_blocks_unlinked_mandatory_ad_hoc_criteria(client, monkeypatch, users):
    monkeypatch.setattr(
        "app.services.bulk_screening._generate_ad_hoc_structured_jd",
        lambda _document: {
            "job_title": "Grounding test",
            "mandatory_requirements": [{"requirement_id": "req_tech_002", "description": "Laravel"}],
            "scoring_rubric": [
                {
                    "criterion_id": "required_skills",
                    "name": "Required skills",
                    "mandatory": True,
                    "requirement_ids": ["req_tech_001"],
                }
            ],
            "extraction_warnings": ["mandatory requirement req_tech_002 was not linked to any scoring criterion"],
        },
    )
    created = client.post(
        "/api/bulk-screening/batches/ad-hoc-jd",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        files={"jd_file": ("full-stack-jd.txt", b"Laravel PHP", "text/plain")},
    )
    assert created.status_code == 200, created.text

    confirmed = client.post(
        f"/api/bulk-screening/batches/{created.json()['id']}/confirm-criteria",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"confirmed": True},
    )

    assert confirmed.status_code == 409


def test_bulk_screening_returns_structured_ad_hoc_requirement_conflicts(client, monkeypatch, users):
    monkeypatch.setattr(
        "app.services.bulk_screening._generate_ad_hoc_structured_jd",
        lambda _document: {
            "schema_version": "structured-jd-v1",
            "job_id": "adhoc",
            "source_document_id": "jd",
            "extraction_method": "live_gemma",
            "job_title": "Assistant Professor",
            "department": "Faculty",
            "mandatory_requirements": [
                {
                    "requirement_id": "req_007",
                    "category": "research",
                    "description": "2+ papers in Scopus/WoS (Assistant Professor)",
                    "requirement_type": "minimum",
                    "mandatory": True,
                    "preferred": False,
                }
            ],
            "preferred_requirements": [],
            "scoring_rubric": [
                {
                    "criterion_id": "crit_004",
                    "name": "Research & Innovation",
                    "category": "research",
                    "description": "Research output",
                    "weight": 100,
                    "mandatory": False,
                    "requirement_ids": ["req_007"],
                }
            ],
        },
    )
    created = client.post(
        "/api/bulk-screening/batches/ad-hoc-jd",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        files={"jd_file": ("faculty-jd.txt", b"research", "text/plain")},
    )
    confirmed = client.post(
        f"/api/bulk-screening/batches/{created.json()['id']}/confirm-criteria",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"confirmed": True},
    )

    assert confirmed.status_code == 409
    assert confirmed.json()["code"] == "INVALID_SCREENING_CRITERIA"
    assert any(issue["type"] == "MANDATORY_LINK_CONFLICT" for issue in confirmed.json()["issues"])

    reconciled = client.post(
        f"/api/bulk-screening/batches/{created.json()['id']}/reconcile-criteria",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"confirmed": True},
    )

    assert reconciled.status_code == 200, reconciled.text
    criterion = reconciled.json()["criteria_snapshot"][0]
    assert criterion["criterion_id"] == "crit_004"
    assert criterion["mandatory"] is True


def test_bulk_screening_confirms_multi_rank_ad_hoc_jd_without_target_designation(client, monkeypatch, users):
    jd_payload = _multi_designation_structured_jd()
    monkeypatch.setattr("app.services.bulk_screening._generate_ad_hoc_structured_jd", lambda _document: jd_payload)
    created = client.post(
        "/api/bulk-screening/batches/ad-hoc-jd",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        files={"jd_file": ("faculty-jd.txt", b"assistant associate professor", "text/plain")},
    )

    confirmed = client.post(
        f"/api/bulk-screening/batches/{created.json()['id']}/confirm-criteria",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"confirmed": True},
    )

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["target_designation"] is None
    assert confirmed.json()["status"] == "READY"


def test_designation_filtered_structured_jd_does_not_require_all_rank_thresholds():
    assistant = validate_structured_jd_for_engine(
        _multi_designation_structured_jd(),
        target_designation="Assistant Professor",
    ).canonical_payload
    professor = validate_structured_jd_for_engine(
        _multi_designation_structured_jd(),
        target_designation="Professor",
    ).canonical_payload

    assistant_text = json.dumps(assistant).lower()
    professor_text = json.dumps(professor).lower()
    assert "minimum 2 years" in assistant_text
    assert "minimum 8 years" not in assistant_text
    assert "minimum 10 years" not in assistant_text
    assert "minimum 10 years" in professor_text
    assert "2+ papers in scopus/wos" not in professor_text
    assert sum(criterion["weight"] for criterion in professor["scoring_rubric"]) == 100


def test_bulk_designation_variant_aggregation_prefers_meeting_variant():
    review = BulkVariantEvaluation(
        designation="Professor",
        result=ProviderExecutionResult(
            provider="test",
            provider_engine_version="test",
            payload={"eligibility": {"status": "REVIEW"}, "criterion_evaluations": []},
        ),
    )
    meets = BulkVariantEvaluation(
        designation="Assistant Professor",
        result=ProviderExecutionResult(
            provider="test",
            provider_engine_version="test",
            payload={"eligibility": {"status": "PASS"}, "criterion_evaluations": []},
        ),
    )

    selected = _strongest_variant_result([review, meets])

    assert selected.designation == "Assistant Professor"


def test_bulk_screening_systemic_failure_stops_remaining_pending_work(client, db_session, users, published_job):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(
        client,
        users["recruiter"]["id"],
        created.json()["id"],
        [
            _resume_file("first.pdf", b"%PDF-1.4 first resume evidence"),
            _resume_file("second.pdf", b"%PDF-1.4 second resume evidence"),
        ],
    )
    assert _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"]).status_code == 200

    class InvalidJDProvider:
        name = "invalid-jd"
        engine_version = "test"

        def evaluate(self, _item):
            from app.services.screening import EngineProviderError

            raise EngineProviderError("INVALID_STRUCTURED_JD", "StructuredJD validation failed at source path")

    assert process_next_bulk_screening_jobs(db_session, provider=InvalidJDProvider()) == 1
    db_session.commit()
    assert process_next_bulk_screening_jobs(db_session, provider=InvalidJDProvider()) == 0
    refreshed = client.get(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    ).json()

    assert refreshed["status"] == "FAILED"
    assert refreshed["failure_code"] == "INVALID_STRUCTURED_JD"
    assert refreshed["failure_message"] == "Screening criteria are not compatible with the current screening engine."
    assert [item["status"] for item in refreshed["items"]].count("PENDING") == 1


def test_bulk_screening_resume_requeues_retryable_failed_items(client, db_session, users, published_job):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(client, users["recruiter"]["id"], created.json()["id"], [_resume_file("technical.pdf")])
    assert _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"]).status_code == 200

    class FailingProvider:
        name = "failing-provider"
        engine_version = "test"

        def evaluate(self, _item):
            raise RuntimeError("synthetic provider failure")

    while process_next_bulk_screening_jobs(db_session, provider=FailingProvider()):
        db_session.commit()

    failed = client.get(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    ).json()
    assert failed["status"] == "FAILED"
    assert failed["items"][0]["status"] == "FAILED"

    resumed = client.post(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}/resume",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )

    work_item = db_session.scalar(select(BulkScreeningWorkItem))
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "QUEUED"
    assert resumed.json()["items"][0]["status"] == "PENDING"
    assert work_item.status.value == "PENDING"
    assert work_item.attempts == 0


def test_bulk_screening_resume_preserves_completed_results_and_pending_work(
    client,
    db_session,
    users,
    published_job,
):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(
        client,
        users["recruiter"]["id"],
        created.json()["id"],
        [
            _resume_file("completed.pdf", b"%PDF-1.4 completed resume evidence"),
            _resume_file("invalid-jd.pdf", b"%PDF-1.4 invalid jd trigger"),
            _resume_file("pending.pdf", b"%PDF-1.4 pending resume evidence"),
        ],
    )
    assert _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"]).status_code == 200

    class MixedSystemicProvider:
        name = "mixed-systemic"
        engine_version = "test"

        def evaluate(self, item):
            if item.original_filename == "completed.pdf":
                return ProviderExecutionResult(
                    provider=self.name,
                    provider_engine_version=self.engine_version,
                    payload={
                        "artifact_schema_version": "candidate-evaluation-v1",
                        "eligibility": {"status": "PASS"},
                        "criterion_evaluations": [],
                        "evidence_completeness": 1,
                    },
                )
            from app.services.screening import EngineProviderError

            raise EngineProviderError("INVALID_STRUCTURED_JD", "StructuredJD validation failed")

    assert process_next_bulk_screening_jobs(db_session, provider=MixedSystemicProvider(), limit=1) == 1
    db_session.commit()
    assert process_next_bulk_screening_jobs(db_session, provider=MixedSystemicProvider(), limit=1) == 1
    db_session.commit()

    failed = client.get(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    ).json()
    assert failed["status"] == "FAILED"
    assert [item["status"] for item in failed["items"]] == ["COMPLETED", "FAILED", "PENDING"]

    work_item_count_before = len(list(db_session.scalars(select(BulkScreeningWorkItem))))
    resumed = client.post(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}/resume",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    work_item_count_after = len(list(db_session.scalars(select(BulkScreeningWorkItem))))

    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "QUEUED"
    assert [item["status"] for item in resumed.json()["items"]] == ["COMPLETED", "PENDING", "PENDING"]
    assert work_item_count_after == work_item_count_before


def test_bulk_screening_candidate_name_maps_from_structured_resume_path(
    client,
    db_session,
    tmp_path: Path,
    users,
    published_job,
):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(client, users["recruiter"]["id"], created.json()["id"], [_resume_file("candidate.pdf")])
    started = _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"])
    assert started.status_code == 200, started.text

    structured_resume = tmp_path / "structured-resume.json"
    structured_resume.write_text(json.dumps({"personal_information": {"full_name": "Synthetic Candidate"}}))

    class NameProvider:
        name = "name-provider"
        engine_version = "test"

        def evaluate(self, item):
            return ProviderExecutionResult(
                provider=self.name,
                provider_engine_version=self.engine_version,
                structured_resume_path=structured_resume,
                payload={
                    "artifact_schema_version": "candidate-evaluation-v1",
                    "eligibility": {"status": "PASS"},
                    "criterion_evaluations": [
                        {
                            "criterion_id": "required",
                            "criterion_name": "Required evidence",
                            "category": "skill",
                            "status": "met",
                            "evidence": [{"source_type": "resume", "source_document_id": item.id, "exact_text": "PHP"}],
                        }
                    ],
                    "evidence_completeness": 1,
                    "experience_summary": {"confirmed_months": 24},
                },
            )

    while process_next_bulk_screening_jobs(db_session, provider=NameProvider()):
        db_session.commit()

    item = db_session.scalar(select(BulkScreeningItem))
    assert item.candidate_name == "Synthetic Candidate"


def test_bulk_screening_missing_resume_evidence_stays_needs_review(
    client,
    db_session,
    users,
    published_job,
):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(client, users["recruiter"]["id"], created.json()["id"], [_resume_file("adjacent.pdf")])
    started = _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"])
    assert started.status_code == 200, started.text

    class AdjacentProvider:
        name = "adjacent-provider"
        engine_version = "test"

        def evaluate(self, item):
            return ProviderExecutionResult(
                provider=self.name,
                provider_engine_version=self.engine_version,
                payload={
                    "artifact_schema_version": "candidate-evaluation-v1",
                    "eligibility": {"status": "FAIL", "failed_requirements": [], "requirement_details": []},
                    "criterion_evaluations": [
                        {
                            "criterion_id": "required",
                            "criterion_name": "Required evidence",
                            "category": "skill",
                            "status": "not_found",
                            "explanation": "Missing required/core components: FastAPI",
                            "evidence_found": ["Python service support"],
                            "missing_information": ["FastAPI is not stated in the resume"],
                            "component_assessment": {
                                "supported_adjacent_components": ["Python service support"],
                                "missing_core_components": ["FastAPI"],
                                "missing_evaluation_dimensions": ["backend ownership"],
                            },
                            "evidence": [
                                {"source_type": "resume", "source_document_id": item.id, "exact_text": "Python"}
                            ],
                        }
                    ],
                    "evidence_completeness": 0.85,
                    "experience_summary": {"confirmed_months": 36},
                    "warnings": ["Verify framework ownership in interview."],
                },
            )

    while process_next_bulk_screening_jobs(db_session, provider=AdjacentProvider()):
        db_session.commit()

    refreshed = client.get(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    item = refreshed.json()["items"][0]
    assert item["classification"] == "NEEDS_REVIEW"
    assert "not demonstrated" in item["concise_reason"].lower()
    assert "No sufficient evidence" not in item["concise_reason"]
    assert item["criterion_results"][0]["raw_component_assessment"]["supported_adjacent_components"] == [
        "Python service support"
    ]


def test_bulk_screening_verified_hard_gate_failure_classifies_does_not_meet(
    client,
    db_session,
    users,
    published_job,
):
    created = _create_existing_batch(client, users["recruiter"]["id"], published_job["id"])
    uploaded = _upload_resumes(client, users["recruiter"]["id"], created.json()["id"], [_resume_file("hard-gate.pdf")])
    started = _start_batch(client, users["recruiter"]["id"], uploaded.json()["id"])
    assert started.status_code == 200, started.text

    class HardGateProvider:
        name = "hard-gate-provider"
        engine_version = "test"

        def evaluate(self, item):
            return ProviderExecutionResult(
                provider=self.name,
                provider_engine_version=self.engine_version,
                payload={
                    "artifact_schema_version": "candidate-evaluation-v1",
                    "eligibility": {
                        "status": "FAIL",
                        "failed_requirements": ["experience"],
                        "requirement_details": [
                            {
                                "requirement_id": "experience",
                                "status": "not_met",
                                "description": "minimum 24 months confirmed experience",
                            }
                        ],
                    },
                    "criterion_evaluations": [
                        {
                            "criterion_id": "experience",
                            "criterion_name": "Required experience",
                            "category": "experience",
                            "status": "not_met",
                            "explanation": "Confirmed experience is below the required threshold.",
                            "missing_information": [],
                            "component_assessment": {},
                            "evidence": [
                                {"source_type": "resume", "source_document_id": item.id, "exact_text": "6 months"}
                            ],
                        }
                    ],
                    "evidence_completeness": 0.95,
                    "experience_summary": {"confirmed_months": 6},
                },
            )

    while process_next_bulk_screening_jobs(db_session, provider=HardGateProvider()):
        db_session.commit()

    refreshed = client.get(
        f"/api/bulk-screening/batches/{uploaded.json()['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    item = refreshed.json()["items"][0]
    assert item["classification"] == "DOES_NOT_MEET_CRITERIA"
    assert "Verified hard-gate evidence" in item["concise_reason"]
    assert "minimum 24 months confirmed experience" in item["concise_reason"]
