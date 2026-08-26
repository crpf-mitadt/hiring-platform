import io
import json
import threading
import zipfile

from app.models import BulkScreeningItem, BulkScreeningWorkItem
from app.services.bulk_screening import process_next_bulk_screening_jobs
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


def _create_existing_batch(client, actor_id: str, job_id: str, files):
    return client.post(
        "/api/bulk-screening/batches/existing-job",
        headers={"X-Actor-Id": actor_id},
        data={"job_id": job_id},
        files=files,
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
        [_resume_file("candidate.pdf")],
    )
    assert candidate.status_code == 403


def test_bulk_screening_creates_existing_job_batch_and_queues_without_inline_provider(
    client,
    db_session,
    users,
    published_job,
):
    response = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
        [_resume_file("first.pdf"), _resume_file("second.pdf", b"%PDF-1.4 missing mandatory Laravel")],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_type"] == "EXISTING_JOB"
    assert body["status"] == "QUEUED"
    assert body["accepted_count"] == 2
    assert body["completed_count"] == 0
    assert len(body["items"]) == 2
    assert all(item["status"] == "PENDING" for item in body["items"])
    assert all(item["provider"] is None for item in body["items"])
    assert db_session.scalar(select(BulkScreeningWorkItem)) is not None
    _assert_no_score_keys(body)


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
        [_resume_file("candidate.pdf")],
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

    uploaded = client.post(
        f"/api/bulk-screening/batches/{batch_id}/resumes",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        files=[_resume_file("candidate.pdf")],
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["status"] == "QUEUED"


def test_bulk_screening_handles_duplicates_and_unsupported_files(client, users, published_job):
    same = b"%PDF-1.4 meets all required evidence"
    response = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
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


def test_bulk_screening_zip_security_rejects_path_traversal_and_nested_zip(client, users, published_job):
    traversal = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
        [_zip_file({"../escape.pdf": b"%PDF-1.4"})],
    )
    assert traversal.status_code == 400

    nested = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
        [_zip_file({"nested.zip": b"PK fake"})],
    )
    assert nested.status_code == 400


def test_bulk_screening_zip_security_rejects_oversized_archive(client, users, published_job):
    response = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
        [_zip_file({"large.pdf": b"x" * (51 * 1024 * 1024)})],
    )
    assert response.status_code == 400


def test_bulk_screening_processes_pass_fail_review_and_technical_failure(
    client,
    db_session,
    users,
    published_job,
):
    response = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
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
    response = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
        [_resume_file("meets.pdf", b"%PDF-1.4 meets all required evidence")],
    )
    assert response.status_code == 200, response.text
    batch_id = response.json()["id"]

    while process_next_bulk_screening_jobs(db_session):
        db_session.commit()

    export = client.get(
        f"/api/bulk-screening/batches/{batch_id}/export.csv",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )

    assert export.status_code == 200
    assert "filename,candidate_name,classification,status" in export.text
    assert "MEETS_CRITERIA" in export.text
    assert "score" not in export.text.lower()
    assert "rank" not in export.text.lower()


def test_bulk_screening_worker_consumes_bulk_queue_with_existing_loop(
    client,
    db_session,
    monkeypatch,
    users,
    published_job,
):
    response = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
        [_resume_file("meets.pdf")],
    )
    assert response.status_code == 200, response.text

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
    first = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
        [_resume_file("Aarav_PrivatePhone9999999999.pdf", content)],
    )
    second = _create_existing_batch(
        client,
        users["recruiter"]["id"],
        published_job["id"],
        [_resume_file("Different_Name_DOB_1990.pdf", content)],
    )
    assert first.status_code == 200
    assert second.status_code == 200

    while process_next_bulk_screening_jobs(db_session):
        db_session.commit()

    items = list(db_session.scalars(select(BulkScreeningItem).order_by(BulkScreeningItem.created_at)))
    assert items[0].classification == items[1].classification


def test_bulk_screening_format_contract(client):
    response = client.get("/api/bulk-screening/formats")
    assert response.status_code == 200
    assert response.json()["jd"] == [".docx", ".md", ".pdf", ".txt"]
    assert response.json()["resumes"] == [".json", ".pdf"]
    assert ".doc" in response.json()["unsupported"]
    assert ".heic" in response.json()["unsupported"]
