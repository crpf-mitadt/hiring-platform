from app.core.config import get_settings


def test_development_actor_provider_is_guarded(client, users):
    settings = get_settings()
    previous = settings.actor_provider
    settings.actor_provider = "external"
    try:
        response = client.get(
            "/api/applications/mine",
            headers={"X-Actor-Id": users["candidate"]["id"]},
        )
    finally:
        settings.actor_provider = previous

    assert response.status_code == 403


def test_public_candidate_registration_is_not_exposed(client):
    register = client.post(
        "/api/auth/register",
        json={
            "email": "new.candidate@example.org",
            "full_name": "New Candidate",
            "password": "candidate-password",
        },
    )
    assert register.status_code == 404


def test_staff_login_and_logout(client, users):
    login = client.post(
        "/api/auth/login",
        json={"email": users["recruiter"]["email"], "password": "recruiter-password"},
    )
    assert login.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == users["recruiter"]["email"]

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_anonymous_can_view_public_jobs_but_not_staff_apis(client, published_job):
    public_jobs = client.get("/api/public/jobs")
    assert public_jobs.status_code == 200
    assert public_jobs.json()[0]["id"] == published_job["id"]

    staff_jobs = client.get("/api/jobs")
    assert staff_jobs.status_code == 401


def test_candidate_session_cannot_access_staff_or_screening_apis(client, users, published_job):
    login = client.post(
        "/api/auth/login",
        json={"email": users["candidate"]["email"], "password": "candidate-password"},
    )
    assert login.status_code == 200

    staff_jobs = client.get("/api/jobs")
    assert staff_jobs.status_code == 403

    resume = client.post(
        "/api/documents/resumes",
        files={
            "file": (
                "candidate-session-resume.json",
                b'{"candidate_id":"candidate-session","schema_version":"structured-resume-v1"}',
                "application/json",
            )
        },
    )
    assert resume.status_code == 200, resume.text

    application = client.post(
        f"/api/applications/jobs/{published_job['id']}/apply",
        json={
            "candidate": {
                "user_id": users["candidate"]["id"],
                "full_name": users["candidate"]["full_name"],
                "email": users["candidate"]["email"],
                "education_profile": {},
                "work_experience_profile": {},
                "resume_document_id": resume.json()["id"],
            },
            "resume_document_id": resume.json()["id"],
        },
    )
    assert application.status_code == 200, application.text

    dossier = client.get(f"/api/applications/{application.json()['id']}/screening-dossier")
    assert dossier.status_code == 403
