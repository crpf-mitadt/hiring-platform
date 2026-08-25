import threading

from app.models import ScreeningRunStatus, User
from app.services.screening import enqueue_screening_run, process_next_screening_job
from app.worker import run_pending_screening_jobs
from conftest import submit_application


class FailingProvider:
    name = "failing-provider"
    engine_version = "failing-v1"

    def evaluate(self, run):
        raise RuntimeError("synthetic model pipeline failure with sensitive internals omitted")


def test_worker_failure_marks_run_failed_and_allows_retry(client, db_session, users, published_job):
    application = submit_application(client, users, published_job)
    recruiter = db_session.get(User, users["recruiter"]["id"])

    run = enqueue_screening_run(
        db_session,
        application_id=application["id"],
        actor=recruiter,
    )
    job = process_next_screening_job(db_session, provider=FailingProvider())
    db_session.commit()

    assert job.status.value == "FAILED"
    assert run.run_status == ScreeningRunStatus.FAILED
    assert run.failure_code == "ENGINE_EXECUTION_FAILED"
    assert "sensitive internals omitted" in run.failure_message
    assert run.application.current_stage.value == "SCREENING_REVIEW"

    retry = client.post(
        f"/api/applications/screening-runs/{run.id}/retry",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )

    assert retry.status_code == 200, retry.text
    assert retry.json()["run_status"] == "PENDING"
    assert retry.json()["id"] != run.id


def test_continuous_worker_consumes_queued_jobs_without_manual_ui_action(
    client, db_session, monkeypatch, users, published_job
):
    first = submit_application(client, users, published_job, actor_key="candidate")
    second = submit_application(client, users, published_job, actor_key="other_candidate")

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

    assert processed == 2
    first_refreshed = client.get(
        f"/api/applications/{first['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    second_refreshed = client.get(
        f"/api/applications/{second['id']}",
        headers={"X-Actor-Id": users["recruiter"]["id"]},
    )
    assert first_refreshed.json()["current_stage"] == "SCREENING_REVIEW"
    assert second_refreshed.json()["current_stage"] == "SCREENING_REVIEW"
