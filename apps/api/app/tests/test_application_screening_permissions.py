from app.models import ApplicationStage
from conftest import submit_application


def test_candidate_application_status_is_safe(client, users, published_job):
    application = submit_application(client, users, published_job)
    mine = client.get("/api/applications/mine", headers={"X-Actor-Id": users["candidate"]["id"]})
    assert mine.status_code == 200
    assert mine.json()[0]["id"] == application["id"]
    assert "score" not in mine.text
    assert "evidence" not in mine.text
    assert "model_endpoint_slot" not in mine.text
    assert "failure_message" not in mine.text


def test_candidate_cannot_access_other_candidate_application(client, users, published_job):
    application = submit_application(client, users, published_job)
    response = client.get(
        f"/api/applications/{application['id']}",
        headers={"X-Actor-Id": users["other_candidate"]["id"]},
    )
    assert response.status_code == 403


def test_candidate_cannot_access_screening_evidence(client, users, published_job):
    application = submit_application(client, users, published_job)
    run = client.post(
        f"/api/applications/{application['id']}/screening-runs",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert run.status_code == 200, run.text
    worker = client.post(
        "/api/screening-jobs/run-next",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert worker.status_code == 200, worker.text
    response = client.get(
        f"/api/applications/{application['id']}/screening",
        headers={"X-Actor-Id": users["candidate"]["id"]},
    )
    assert response.status_code == 403


def test_mock_screening_moves_application_to_review_and_persists_evidence(client, users, published_job):
    application = submit_application(client, users, published_job)
    run = client.post(
        f"/api/applications/{application['id']}/screening-runs",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert run.status_code == 200, run.text
    payload = run.json()
    assert payload["run_status"] == "PENDING"

    duplicate = client.post(
        f"/api/applications/{application['id']}/screening-runs",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["id"] == payload["id"]

    worker = client.post(
        "/api/screening-jobs/run-next",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert worker.status_code == 200, worker.text
    completed_run = worker.json()["screening_run"]
    assert completed_run["run_status"] == "COMPLETED"
    assert completed_run["engine_contract_version"] == "candidate-evaluation-v1/platform-mapper-v1"
    assert completed_run["structured_jd_sha256"] is None
    assert completed_run["eligibility"] in {"PASS", "REVIEW"}
    assert completed_run["score"] > 0
    assert completed_run["criterion_results"]
    assert completed_run["criterion_results"][0]["evidence"]

    refreshed = client.get(
        f"/api/applications/{application['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert refreshed.json()["current_stage"] == ApplicationStage.SCREENING_REVIEW.value


def test_human_screening_decisions_require_remarks(client, users, published_job):
    application = submit_application(client, users, published_job)
    run = client.post(
        f"/api/applications/{application['id']}/screening-runs",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert run.status_code == 200, run.text
    worker = client.post(
        "/api/screening-jobs/run-next",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert worker.status_code == 200, worker.text
    missing_remarks = client.post(
        f"/api/applications/{application['id']}/shortlist",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={},
    )
    assert missing_remarks.status_code == 409

    shortlist = client.post(
        f"/api/applications/{application['id']}/shortlist",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"remarks": "Synthetic reviewer remark supporting assessment shortlist."},
    )
    assert shortlist.status_code == 200
    assert shortlist.json()["current_stage"] == "SHORTLISTED_FOR_ASSESSMENT"

    dossier = client.get(
        f"/api/applications/{application['id']}/screening-dossier",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert dossier.status_code == 200, dossier.text
    assert dossier.json()["decisions"][0]["remarks"] == "Synthetic reviewer remark supporting assessment shortlist."


def test_invalid_transition_fails(client, users, published_job):
    application = submit_application(client, users, published_job)
    response = client.post(
        f"/api/applications/{application['id']}/shortlist",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"remarks": "Too early."},
    )
    assert response.status_code == 409
