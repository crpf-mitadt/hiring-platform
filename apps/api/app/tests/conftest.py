import pytest
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Role
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def create_user(client: TestClient, *, email: str, full_name: str, roles: list[Role]) -> dict:
    response = client.post(
        "/api/users",
        json={"email": email, "full_name": full_name, "roles": [role.value for role in roles]},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def users(client):
    return {
        "candidate": create_user(
            client,
            email="candidate@example.org",
            full_name="Synthetic Candidate",
            roles=[Role.CANDIDATE],
        ),
        "other_candidate": create_user(
            client,
            email="other@example.org",
            full_name="Other Candidate",
            roles=[Role.CANDIDATE],
        ),
        "recruiter": create_user(
            client,
            email="recruiter@example.org",
            full_name="Synthetic Recruiter",
            roles=[Role.HR_RECRUITER],
        ),
        "reviewer": create_user(
            client,
            email="reviewer@example.org",
            full_name="Synthetic Reviewer",
            roles=[Role.DEPARTMENT_REVIEWER],
        ),
        "admin": create_user(
            client,
            email="admin@example.org",
            full_name="Synthetic Admin",
            roles=[Role.HIRING_ADMIN],
        ),
    }


@pytest.fixture()
def org(client):
    school = client.post("/api/schools", json={"name": "Synthetic School"}).json()
    department = client.post(
        "/api/departments", json={"school_id": school["id"], "name": "Synthetic Department"}
    ).json()
    return {"school": school, "department": department}


@pytest.fixture()
def draft_job(client, users, org):
    response = client.post(
        "/api/jobs",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
        json={
            "title": "Assistant Professor",
            "school_id": org["school"]["id"],
            "department_id": org["department"]["id"],
            "designation": "Assistant Professor",
            "employment_type": "Full Time",
            "vacancy_count": 2,
            "location": "Pune",
            "description": "Synthetic JD text for testing.",
            "jd_document_ref": "synthetic-jd-ref",
            "recruiter_id": users["recruiter"]["id"],
            "hiring_manager_id": users["reviewer"]["id"],
            "department_reviewer_ids": [users["reviewer"]["id"]],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def published_job(client, users, draft_job):
    response = client.post(
        f"/api/jobs/{draft_job['id']}/publish",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def submit_application(client, users, published_job, actor_key="candidate") -> dict:
    actor = users[actor_key]
    response = client.post(
        f"/api/applications/jobs/{published_job['id']}/apply",
        headers={"X-Actor-Id": actor["id"]},
        json={
            "candidate": {
                "user_id": actor["id"],
                "full_name": actor["full_name"],
                "email": actor["email"],
                "phone": "0000000000",
                "education_profile": {"highest_degree": "Synthetic degree"},
                "work_experience_profile": {"summary": "Synthetic experience"},
                "resume_document_ref": "synthetic-resume-ref",
            },
            "resume_document_ref": "synthetic-resume-ref",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()

