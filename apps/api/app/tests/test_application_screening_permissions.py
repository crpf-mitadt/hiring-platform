from app.models import ApplicationStage
from conftest import submit_application


def test_candidate_application_status_is_safe(client, users, published_job):
    application = submit_application(client, users, published_job)
    mine = client.get("/api/applications/mine", headers={"X-Actor-Id": users["candidate"]["id"]})
    assert mine.status_code == 200
    assert mine.json()[0]["id"] == application["id"]
    assert "score" not in mine.text
    assert "evidence" not in mine.text


def test_candidate_cannot_access_other_candidate_application(client, users, published_job):
    application = submit_application(client, users, published_job)
    response = client.get(
        f"/api/applications/{application['id']}",
        headers={"X-Actor-Id": users["other_candidate"]["id"]},
    )
    assert response.status_code == 403


def test_candidate_cannot_access_screening_evidence(client, users, published_job):
    application = submit_application(client, users, published_job)
    client.post(
        f"/api/applications/{application['id']}/screening-runs",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
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
    assert payload["run_status"] == "COMPLETE"
    assert payload["eligibility"] in {"PASS", "REVIEW"}
    assert payload["score"] > 0
    assert payload["criterion_results"]
    assert payload["criterion_results"][0]["evidence"]

    refreshed = client.get(
        f"/api/applications/{application['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert refreshed.json()["current_stage"] == ApplicationStage.SCREENING_REVIEW.value


def test_human_screening_decisions_require_remarks(client, users, published_job):
    application = submit_application(client, users, published_job)
    client.post(
        f"/api/applications/{application['id']}/screening-runs",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
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


def test_invalid_transition_fails(client, users, published_job):
    application = submit_application(client, users, published_job)
    response = client.post(
        f"/api/applications/{application['id']}/shortlist",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"remarks": "Too early."},
    )
    assert response.status_code == 409
