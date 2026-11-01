"""Background task framework: tracking rows, retries, permanent failures, alerts."""

from sqlalchemy import select

from app.models import BackgroundTask, Notification
from app.tasks import tracking
from app.tasks.tracking import PermanentError, enqueue, tracked
from tests.factories import make_user
from tests.test_applications import give_resume
from tests.test_jobs_api import make_job

calls: dict[str, int] = {}


@tracked("test_flaky")
def flaky(n_failures: int) -> dict:
    calls["flaky"] = calls.get("flaky", 0) + 1
    if calls["flaky"] <= n_failures:
        raise ConnectionError("redis blipped")
    return {"ok": True}


@tracked("test_permanent")
def permanent(alert: bool) -> None:
    raise PermanentError("bad input", alert=alert)


gave_up: list[tuple] = []


@tracked("test_broken", on_give_up=lambda *args: gave_up.append(args))
def broken(x: int) -> None:
    raise ValueError("bug")


def _row(db, task_id: str) -> BackgroundTask:
    db.expire_all()
    return db.get(BackgroundTask, task_id)


def test_success_is_tracked(db, monkeypatch):
    monkeypatch.setattr(tracking, "backoff_seconds", lambda r: 0)
    calls.clear()
    tid = enqueue(flaky, 0)
    row = _row(db, tid)
    assert row.status == "succeeded"
    assert row.attempts == 1
    assert row.result == {"ok": True}
    assert row.kind == "test_flaky"
    assert row.finished_at is not None


def test_transient_errors_are_retried_then_succeed(db, monkeypatch):
    monkeypatch.setattr(tracking, "backoff_seconds", lambda r: 0)
    calls.clear()
    tid = enqueue(flaky, 2)
    row = _row(db, tid)
    assert row.status == "succeeded"
    assert row.attempts == 3
    assert row.error is None


def test_retries_exhausted_fails_alerts_admins_once_and_calls_give_up(db, monkeypatch):
    monkeypatch.setattr(tracking, "backoff_seconds", lambda r: 0)
    admin = make_user(db, "admin@example.com", "admin")
    gave_up.clear()
    tid = enqueue(broken, 7)
    row = _row(db, tid)
    assert row.status == "failed"
    assert row.attempts == 4  # first try + TASK_MAX_RETRIES (3)
    assert "ValueError: bug" in row.error
    assert gave_up == [(7, row.error)]

    alerts = list(db.scalars(select(Notification).where(Notification.user_id == admin.id)))
    assert [a.type for a in alerts] == ["task_failed"]
    assert alerts[0].payload["task_id"] == tid

    # A second failure of the same kind within the hour does not notify again.
    enqueue(broken, 8)
    assert db.scalar(select(Notification.id).where(Notification.id != alerts[0].id)) is None


def test_permanent_error_fails_without_retry(db):
    make_user(db, "admin@example.com", "admin")
    tid = enqueue(permanent, False)
    row = _row(db, tid)
    assert row.status == "rejected"  # bad input, not an outage: no failure, no alert
    assert row.attempts == 1
    assert row.error == "bad input"
    assert db.scalar(select(Notification.id)) is None
    tid = enqueue(permanent, True)
    assert _row(db, tid).status == "failed"
    assert db.scalar(select(Notification.id)) is not None


def test_queue_down_runs_task_inline(db, monkeypatch):
    calls.clear()

    def no_broker(*a, **k):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(flaky, "apply_async", no_broker)
    tid = enqueue(flaky, 0)
    assert _row(db, tid).status == "succeeded"


def test_notifications_are_emailed_in_background(client, db, caplog):
    import logging

    rec = make_user(db, "rec@example.com", "recruiter")
    job = make_job(db, rec, title="Python Developer")
    from tests.factories import login

    make_user(db, "seeker@example.com")
    h = login(client, "seeker@example.com")
    give_resume(client, h)
    with caplog.at_level(logging.INFO, logger="hike.email"):
        assert (
            client.post("/api/applications", json={"job_id": job.id}, headers=h).status_code == 201
        )
    n = db.scalar(select(Notification).where(Notification.user_id == rec.id))
    db.refresh(n)
    assert n.emailed_at is not None
    assert any("to=rec@example.com" in r.getMessage() for r in caplog.records)
    task = db.scalar(select(BackgroundTask).where(BackgroundTask.kind == "deliver_email"))
    assert task.status == "succeeded"
    assert task.ref_id == n.id


def test_job_update_rescores_applicants(client, db):
    from tests.factories import auth_headers, login

    rec, rh = auth_headers(db, client, "rec@example.com", "recruiter")
    job = make_job(db, rec, title="Python Developer")
    make_user(db, "seeker@example.com")
    h = login(client, "seeker@example.com")
    give_resume(client, h)
    client.post("/api/applications", json={"job_id": job.id}, headers=h)
    res = client.patch(
        f"/api/recruiter/jobs/{job.id}", json={"skills": ["Python", "Go"]}, headers=rh
    )
    assert res.status_code == 200
    kinds = [
        t.kind
        for t in db.scalars(
            select(BackgroundTask)
            .where(BackgroundTask.ref_type == "job")
            .order_by(BackgroundTask.created_at)
        )
    ]
    assert "embed_job" in kinds and "score_job_candidates" in kinds
    scored = db.scalar(select(BackgroundTask).where(BackgroundTask.kind == "score_job_candidates"))
    assert scored.status == "succeeded" and scored.result == {"scored": 1}


def test_admin_system_page_lists_failures(client, db, monkeypatch):
    from tests.factories import auth_headers

    monkeypatch.setattr(tracking, "backoff_seconds", lambda r: 0)
    _, ah = auth_headers(db, client, "admin@example.com", "admin")
    _, sh = auth_headers(db, client, "s@example.com")
    enqueue(broken, 1)
    res = client.get("/api/admin/system", headers=ah)
    assert res.status_code == 200
    body = res.json()
    assert body["dependencies"]["postgres"]["ok"] is True
    assert body["worker"] == "inline"
    assert body["tasks_last_24h"]["failed"] == 1
    assert body["recent_failures"][0]["kind"] == "test_broken"
    assert body["security"]["files_encrypted"] is True
    assert client.get("/api/admin/system", headers=sh).status_code == 403
