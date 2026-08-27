import io
import json
import threading
import zipfile
from pathlib import Path

from app.models import BulkScreeningItem, BulkScreeningWorkItem
from app.services.bulk_screening import process_next_bulk_screening_jobs
from app.services.screening import ProviderExecutionResult
from app.worker import run_pending_screening_jobs
from sqlalchemy import select


def _resume_file(filename: str, content: bytes | None = None):
    return ("files", (filename, content or b"%PDF-1.4 meets all required evidence", "application/pdf"))


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
