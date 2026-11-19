from app.core.config import get_settings
from conftest import upload_resume


def test_resume_upload_stores_metadata_and_checksum(client, users):
    document = upload_resume(client, users["candidate"])

    assert document["purpose"] == "resume"
    assert document["original_filename"] == "synthetic-resume.json"
    assert document["sha256"]
    assert document["size_bytes"] > 0
    assert "storage_key" not in document


def test_document_upload_rejects_path_traversal_filename(client, users):
    response = client.post(
        "/api/documents/resumes",
        headers={"X-Actor-Id": users["candidate"]["id"]},
        files={"file": ("../resume.json", b"{}", "application/json")},
    )

    assert response.status_code == 400


def test_document_upload_rejects_unsupported_resume_extension(client, users):
    response = client.post(
        "/api/documents/resumes",
        headers={"X-Actor-Id": users["candidate"]["id"]},
        files={"file": ("resume.docx", b"not supported for screening input", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_document_upload_rejects_oversized_payload(client, users):
    get_settings().max_upload_bytes = 8
    response = client.post(
        "/api/documents/resumes",
        headers={"X-Actor-Id": users["candidate"]["id"]},
        files={"file": ("resume.json", b'{"too":"large"}', "application/json")},
    )

    assert response.status_code == 400


def test_candidate_cannot_attach_another_candidates_resume(client, users, published_job):
    document = upload_resume(client, users["other_candidate"])

    response = client.post(
        f"/api/applications/jobs/{published_job['id']}/apply",
        headers={"X-Actor-Id": users["candidate"]["id"]},
        json={
            "candidate": {
                "user_id": users["candidate"]["id"],
                "full_name": users["candidate"]["full_name"],
                "email": users["candidate"]["email"],
                "resume_document_id": document["id"],
            },
            "resume_document_id": document["id"],
        },
    )

    assert response.status_code == 403
