"""Dead-letter retry, idempotent tasks, and recovery of tasks left by a dead worker."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.models import BackgroundTask, Notification, Resume
from app.services import resume_parser
from app.services.notifications import send_email
from app.services.resume_parser import PDF_MIME
from app.services.saved_searches import alert_for_job
from app.tasks import tracking
from app.tasks.tracking import enqueue, recover_stale_tasks, tracked
from tests.factories import auth_headers, make_user, post_resume
from tests.test_jobs_api import make_job

PDF = (Path(__file__).parent / "fixtures" / "priya_sharma_backend.pdf").read_bytes()
state = {"fail": True, "runs": 0}


@tracked("test_dead_letter")
def sometimes_broken(x: int) -> dict:
    state["runs"] += 1
    if state["fail"]:
        raise RuntimeError("dependency down")
    return {"x": x}


def _row(db, task_id):
    db.expire_all()
    return db.get(BackgroundTask, task_id)


def test_dead_letter_retry_by_admin(client, db, monkeypatch):
    monkeypatch.setattr(tracking, "backoff_seconds", lambda r: 0)
    _, ah = auth_headers(db, client, "admin@example.com", "admin")
    _, sh = auth_headers(db, client, "s@example.com")
    state.update(fail=True, runs=0)
    tid = enqueue(sometimes_broken, 5)
    assert _row(db, tid).status == "failed"
    system = client.get("/api/admin/system", headers=ah).json()
    assert system["dead_letter"] == 1
    assert "hike_dead_letter_tasks 1.0" in client.get("/metrics").text

    assert client.post(f"/api/admin/tasks/{tid}/retry", headers=sh).status_code == 403
    state["fail"] = False  # the dependency is back
    res = client.post(f"/api/admin/tasks/{tid}/retry", headers=ah)
    assert res.status_code == 200
    new = _row(db, res.json()["task_id"])
    assert new.status == "succeeded" and new.result == {"x": 5} and new.args == [5]
    assert _row(db, tid).result["retried_as"] == new.id
    assert client.get("/api/admin/system", headers=ah).json()["dead_letter"] == 0
    # A task is retried at most once, and only failed tasks can be retried.
    assert client.post(f"/api/admin/tasks/{tid}/retry", headers=ah).status_code == 409
    assert client.post(f"/api/admin/tasks/{new.id}/retry", headers=ah).status_code == 409
    assert client.post("/api/admin/tasks/nope/retry", headers=ah).status_code == 409
    entry = client.get("/api/admin/audit", params={"action": "admin.task"}, headers=ah).json()
    assert entry["items"][0]["details"]["task_id"] == tid


def test_failed_resume_parse_can_be_retried(client, db, monkeypatch):
    monkeypatch.setattr(tracking, "backoff_seconds", lambda r: 0)
    _, ah = auth_headers(db, client, "admin@example.com", "admin")
    _, sh = auth_headers(db, client, "s@example.com")
    real = resume_parser.extract_text_safely

    def outage(*a, **k):
        raise OSError("storage unavailable")

    monkeypatch.setattr("app.services.resumes.extract_text_safely", outage)
    body = post_resume(client, sh, "cv.pdf", PDF, PDF_MIME).json()
    assert body["status"] == "failed"
    assert "try uploading it again" in body["parse_error"]
    task = db.scalar(select(BackgroundTask).where(BackgroundTask.kind == "process_resume"))
    assert task.status == "failed" and task.attempts == 4

    monkeypatch.setattr("app.services.resumes.extract_text_safely", real)
    assert client.post(f"/api/admin/tasks/{task.id}/retry", headers=ah).status_code == 200
    resume = client.get(f"/api/resumes/{body['id']}", headers=sh).json()
    assert resume["status"] == "ready" and resume["parse_error"] is None


def test_resume_processing_is_idempotent(client, db):
    from app.services.resumes import process_resume_file

    _, h = auth_headers(db, client, "s@example.com")
    rid = post_resume(client, h, "cv.pdf", PDF, PDF_MIME).json()["id"]
    assert process_resume_file(db, rid) == {"skipped": "already ready"}


def test_resume_processing_skips_a_row_locked_by_another_worker(client, db):
    from app.db.session import SessionLocal
    from app.services.resumes import process_resume_file

    _, h = auth_headers(db, client, "s@example.com")
    rid = post_resume(client, h, "cv.pdf", PDF, PDF_MIME).json()["id"]
    r = db.get(Resume, rid)
    r.status = "processing"
    db.commit()
    with SessionLocal() as other:
        other.scalar(select(Resume).where(Resume.id == rid).with_for_update())
        with SessionLocal() as mine:
            assert process_resume_file(mine, rid) == {"skipped": "locked or deleted"}


def test_email_delivery_is_idempotent(client, db, caplog):
    import logging

    from app.db.session import SessionLocal

    user = make_user(db, "s@example.com")
    n = Notification(user_id=user.id, type="t", title="Hello", body="b")
    db.add(n)
    db.commit()
    # Another worker is sending it right now: this one backs off.
    with SessionLocal() as other:
        other.scalar(select(Notification).where(Notification.id == n.id).with_for_update())
        with SessionLocal() as mine:
            assert send_email(mine, n.id) == {"skipped": "being sent by another worker"}
    with caplog.at_level(logging.INFO, logger="hike.email"):
        with SessionLocal() as s:
            assert send_email(s, n.id)["backend"] == "log"
        with SessionLocal() as s:
            assert send_email(s, n.id) == {"skipped": "already sent"}
    sent = [r for r in caplog.records if "subject='Hello'" in r.getMessage()]
    assert len(sent) == 1
    assert sent[0].message_id == f"<notification-{n.id}@hike>"


def test_saved_search_alerts_are_idempotent(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    seeker, h = auth_headers(db, client, "s@example.com")
    client.post("/api/saved-searches", json={"name": "py", "params": {"q": "python"}}, headers=h)
    job = make_job(db, rec, title="Python Developer")
    assert alert_for_job(db, job.id) == {"notified": 1}
    assert alert_for_job(db, job.id) == {"notified": 0}
    count = db.scalars(select(Notification).where(Notification.type == "saved_search_match"))
    assert len(list(count)) == 1


def test_stale_tasks_are_recovered_on_worker_start(db, monkeypatch):
    sent = []
    monkeypatch.setattr(
        sometimes_broken, "apply_async", lambda args, task_id: sent.append((task_id, args))
    )
    old = datetime.now(UTC) - timedelta(minutes=30)
    db.add_all(
        [
            BackgroundTask(id="stale-queued", kind="test_dead_letter", args=[1], created_at=old),
            BackgroundTask(
                id="stale-running",
                kind="test_dead_letter",
                args=[2],
                status="running",
                created_at=old,
                started_at=old,
            ),
            BackgroundTask(id="fresh-queued", kind="test_dead_letter", args=[3]),
            BackgroundTask(
                id="done", kind="test_dead_letter", args=[4], status="succeeded", created_at=old
            ),
        ]
    )
    db.commit()
    assert recover_stale_tasks() == 2
    assert sorted(sent) == [("stale-queued", [1]), ("stale-running", [2])]
