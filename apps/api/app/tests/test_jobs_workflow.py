def test_job_lifecycle_allows_draft_publish_close(client, users, draft_job):
    patch_response = client.patch(
        f"/api/jobs/{draft_job['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"location": "Mumbai"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["location"] == "Mumbai"

    publish_response = client.post(
        f"/api/jobs/{draft_job['id']}/publish",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "PUBLISHED"

    edit_published = client.patch(
        f"/api/jobs/{draft_job['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"location": "Delhi"},
    )
    assert edit_published.status_code == 409

    close_response = client.post(
        f"/api/jobs/{draft_job['id']}/close",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "CLOSED"

    close_again = client.post(
        f"/api/jobs/{draft_job['id']}/close",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert close_again.status_code == 409


def test_candidate_cannot_create_job(client, users, org):
    response = client.post(
        "/api/jobs",
        headers={"X-Actor-Id": users["candidate"]["id"]},
        json={
            "title": "Synthetic Job",
            "school_id": org["school"]["id"],
            "department_id": org["department"]["id"],
            "designation": "Faculty",
            "employment_type": "Full Time",
            "vacancy_count": 1,
            "location": "Pune",
            "description": "Synthetic",
            "recruiter_id": users["recruiter"]["id"],
            "hiring_manager_id": users["reviewer"]["id"],
            "department_reviewer_ids": [],
        },
    )
    assert response.status_code == 403


def test_rubric_version_can_be_approved_but_changes_create_new_version(client, users, draft_job):
    version = client.post(
        f"/api/jobs/{draft_job['id']}/rubric-versions",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={
            "criteria": [
                {
                    "criterion_id": "c1",
                    "name": "Teaching evidence",
                    "category": "teaching",
                    "weight": 100,
                }
            ],
            "engine_mapping": {"future_schema": "structured-jd-v1.scoring_rubric"},
        },
    )
    assert version.status_code == 200
    assert version.json()["version_number"] == 1

    approved = client.post(
        f"/api/rubric-versions/{version.json()['id']}/approve",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    replacement = client.post(
        f"/api/jobs/{draft_job['id']}/rubric-versions",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={"criteria": [], "engine_mapping": {}},
    )
    assert replacement.status_code == 200
    assert replacement.json()["version_number"] == 2

