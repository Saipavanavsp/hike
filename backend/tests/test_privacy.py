"""Resume deletion, account erasure and the retention policy."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import settings
from app.models import (
    Application,
    MatchScore,
    Notification,
    RefreshToken,
    Resume,
    SeekerProfile,
    User,
)
from app.services.resume_parser import PDF_MIME
from app.services.retention import run_retention
from tests.factories import PASSWORD, auth_headers, make_user, post_resume
from tests.test_applications import give_resume
from tests.test_jobs_api import make_job

FIXTURES = Path(__file__).parent / "fixtures"
PDF = (FIXTURES / "priya_sharma_backend.pdf").read_bytes()


def _stored(key: str) -> bool:
    return (Path(os.environ["STORAGE_DIR"]) / key).exists()


def _count(db, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


def test_delete_resume_removes_file_and_derived_data(client, db):
    rec, rh = auth_headers(db, client, "rec@example.com", "recruiter")
    job = make_job(db, rec, title="Python Developer")
    user, h = auth_headers(db, client, "s@example.com")
    rid = give_resume(client, h)
    assert client.post("/api/applications", json={"job_id": job.id}, headers=h).status_code == 201
    client.get(f"/api/recruiter/jobs/{job.id}/applications", headers=rh)  # caches a score
    key = db.get(Resume, rid).storage_key
    assert _stored(key) and _count(db, MatchScore, MatchScore.resume_id == rid) == 1

    assert client.delete(f"/api/resumes/{rid}", headers=h).status_code == 204
    db.expire_all()
    assert db.get(Resume, rid) is None
    assert not _stored(key)
    assert _count(db, MatchScore, MatchScore.resume_id == rid) == 0

    # The application record stays for the recruiter, without any resume data.
    app = db.scalar(select(Application).where(Application.seeker_id == user.id))
    assert app.resume_id is None
    rows = client.get(f"/api/recruiter/jobs/{job.id}/applications", headers=rh).json()
    assert rows[0]["resume"] is None and rows[0]["match"] is None
    assert client.get("/api/resumes/current", headers=h).status_code == 404


def test_delete_account_erases_everything(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    job = make_job(db, rec, title="Python Developer")
    user, h = auth_headers(db, client, "s@example.com")
    give_resume(client, h)
    second = post_resume(client, h, "cv.pdf", PDF, PDF_MIME).json()["id"]
    client.post("/api/applications", json={"job_id": job.id}, headers=h)
    keys = list(db.scalars(select(Resume.storage_key).where(Resume.user_id == user.id)))
    assert len(keys) == 2 and second

    res = client.post("/api/account/delete", json={"password": "wrong"}, headers=h)
    assert res.status_code == 403
    assert db.get(User, user.id) is not None

    uid = user.id
    res = client.post("/api/account/delete", json={"password": PASSWORD}, headers=h)
    assert res.status_code == 204
    db.expire_all()
    assert db.get(User, uid) is None
    assert db.get(SeekerProfile, uid) is None
    for model, col in (
        (Resume, Resume.user_id),
        (Application, Application.seeker_id),
        (RefreshToken, RefreshToken.user_id),
        (Notification, Notification.user_id),
    ):
        assert _count(db, model, col == uid) == 0, model.__name__
    assert not any(_stored(k) for k in keys)
    # The old access token and password no longer work.
    assert client.get("/api/auth/me", headers=h).status_code == 401
    res = client.post("/api/auth/login", json={"email": "s@example.com", "password": PASSWORD})
    assert res.status_code == 401
    # The recruiter's job is untouched.
    assert db.get(type(job), job.id) is not None


def test_only_seekers_can_self_delete(client, db):
    _, rh = auth_headers(db, client, "rec@example.com", "recruiter")
    res = client.post("/api/account/delete", json={"password": PASSWORD}, headers=rh)
    assert res.status_code == 403
    assert client.post("/api/account/delete", json={"password": PASSWORD}).status_code == 401


def _age(db, resume_id: int, days: int) -> None:
    r = db.get(Resume, resume_id)
    r.created_at = datetime.now(UTC) - timedelta(days=days)
    db.commit()


def test_retention_policy(client, db, monkeypatch):
    monkeypatch.setattr(settings, "retention_unconfirmed_days", 7)
    monkeypatch.setattr(settings, "retention_old_resume_days", 365)
    _, h = auth_headers(db, client, "s@example.com")
    current = give_resume(client, h)
    superseded_old = post_resume(client, h, "a.pdf", PDF, PDF_MIME).json()["id"]
    unconfirmed_old = post_resume(client, h, "b.pdf", PDF, PDF_MIME).json()["id"]
    unconfirmed_new = post_resume(client, h, "c.pdf", PDF, PDF_MIME).json()["id"]
    db.get(Resume, superseded_old).confirmed_at = datetime.now(UTC)
    db.commit()
    _age(db, current, 400)  # the current resume is never removed, however old
    _age(db, superseded_old, 400)
    _age(db, unconfirmed_old, 10)

    out = run_retention(db)
    assert out == {"unconfirmed_resumes": 1, "old_resumes": 1, "inactive_seekers": 0}
    db.expire_all()
    remaining = set(db.scalars(select(Resume.id)))
    assert remaining == {current, unconfirmed_new}


def test_inactive_seeker_retention(client, db, monkeypatch):
    monkeypatch.setattr(settings, "retention_inactive_seeker_days", 730)
    stale = make_user(db, "stale@example.com")
    stale.last_login_at = datetime.now(UTC) - timedelta(days=800)
    make_user(db, "fresh@example.com")
    rec = make_user(db, "rec@example.com", "recruiter")
    rec.last_login_at = datetime.now(UTC) - timedelta(days=800)  # recruiters are not swept
    db.commit()
    assert run_retention(db)["inactive_seekers"] == 1
    db.expire_all()
    emails = set(db.scalars(select(User.email)))
    assert emails == {"fresh@example.com", "rec@example.com"}


def test_admin_can_trigger_retention(client, db):
    _, ah = auth_headers(db, client, "admin@example.com", "admin")
    res = client.post("/api/admin/retention/run", headers=ah)
    assert res.status_code == 200
    task = client.get(f"/api/tasks/{res.json()['task_id']}", headers=ah).json()
    assert task["status"] == "succeeded"
    _, sh = auth_headers(db, client, "s@example.com")
    assert client.post("/api/admin/retention/run", headers=sh).status_code == 403
