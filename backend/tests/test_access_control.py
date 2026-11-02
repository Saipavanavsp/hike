"""Security hardening: an access table for every API route, cross-account ownership checks,
CSRF on cookie endpoints, security headers, and upload/download attack cases."""

import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import BackgroundTask, Resume
from app.services.resume_parser import PDF_MIME
from tests.factories import auth_headers, fetch_resume_file, post_resume
from tests.test_applications import give_resume
from tests.test_jobs_api import make_job

PDF = (Path(__file__).parent / "fixtures" / "priya_sharma_backend.pdf").read_bytes()

# Who may call each route. public = anyone; any = any signed-in user (ownership is checked
# inside); seeker / recruiter (recruiters and admins) / admin = role required.
ACCESS = {
    "GET /health": "public",
    "GET /api/health": "public",
    "POST /api/auth/register": "public",
    "POST /api/auth/login": "public",
    "POST /api/auth/refresh": "public",
    "POST /api/auth/logout": "public",
    "GET /api/auth/me": "any",
    "GET /api/jobs": "public",
    "GET /api/jobs/autocomplete": "public",
    "GET /api/jobs/saved": "seeker",
    "GET /api/jobs/{job_id}": "public",
    "POST /api/jobs/{job_id}/save": "seeker",
    "DELETE /api/jobs/{job_id}/save": "seeker",
    "GET /api/recruiter/jobs": "recruiter",
    "POST /api/recruiter/jobs": "recruiter",
    "GET /api/recruiter/jobs/{job_id}": "recruiter",
    "PATCH /api/recruiter/jobs/{job_id}": "recruiter",
    "POST /api/recruiter/jobs/{job_id}/close": "recruiter",
    "POST /api/recruiter/jobs/{job_id}/reopen": "recruiter",
    "GET /api/recruiter/jobs/{job_id}/applications": "recruiter",
    "PATCH /api/recruiter/applications/{application_id}/status": "recruiter",
    "GET /api/recruiter/analytics": "recruiter",
    "GET /api/recruiter/stats/applications-weekly": "recruiter",
    "POST /api/recruiter/applications/{application_id}/interviews": "recruiter",
    "PATCH /api/recruiter/interviews/{interview_id}": "recruiter",
    "POST /api/recruiter/interviews/{interview_id}/cancel": "recruiter",
    "GET /api/recruiter/company": "recruiter",
    "PUT /api/recruiter/company": "recruiter",
    "GET /api/resumes": "seeker",
    "POST /api/resumes": "seeker",
    "GET /api/resumes/current": "seeker",
    "GET /api/resumes/{resume_id}": "seeker",
    "PUT /api/resumes/{resume_id}": "seeker",
    "DELETE /api/resumes/{resume_id}": "seeker",
    "POST /api/resumes/{resume_id}/link": "any",
    "GET /api/tasks/{task_id}": "any",
    "GET /api/skills": "public",
    "GET /api/stats/public": "public",
    "GET /api/applications": "seeker",
    "POST /api/applications": "seeker",
    "GET /api/applications/{application_id}": "any",
    "GET /api/notifications": "any",
    "POST /api/notifications/{notification_id}/read": "any",
    "POST /api/notifications/read-all": "any",
    "GET /api/profile": "seeker",
    "PUT /api/profile": "seeker",
    "GET /api/account/preferences": "any",
    "PUT /api/account/preferences": "any",
    "POST /api/account/delete": "any",
    "GET /api/admin/users": "admin",
    "POST /api/admin/users/deactivate": "admin",
    "POST /api/admin/users/activate": "admin",
    "GET /api/admin/jobs": "admin",
    "POST /api/admin/jobs/close": "admin",
    "GET /api/admin/system": "admin",
    "POST /api/admin/retention/run": "admin",
    "POST /api/admin/tasks/{task_id}/retry": "admin",
    "GET /api/admin/audit": "admin",
    "GET /api/admin/applications": "admin",
    "GET /api/interviews": "any",
    "GET /api/interviews/{interview_id}/ics": "any",
    "GET /api/saved-searches": "seeker",
    "POST /api/saved-searches": "seeker",
    "PATCH /api/saved-searches/{search_id}": "seeker",
    "DELETE /api/saved-searches/{search_id}": "seeker",
    "GET /api/companies/{slug}": "public",
}
ALLOWED = {
    "public": {"anon", "seeker", "recruiter", "admin"},
    "any": {"seeker", "recruiter", "admin"},
    "seeker": {"seeker"},
    "recruiter": {"recruiter", "admin"},
    "admin": {"admin"},
}


def test_every_route_is_classified(client):
    from app.main import app

    routes = {f"{m.upper()} {p}" for p, ops in app.openapi()["paths"].items() for m in ops}
    assert routes == set(
        ACCESS
    ), f"unclassified: {sorted(routes - set(ACCESS))}, stale: {sorted(set(ACCESS) - routes)}"


@pytest.fixture
def identities(client, db):
    _, sh = auth_headers(db, client, "s@example.com")
    _, rh = auth_headers(db, client, "r@example.com", "recruiter")
    _, ah = auth_headers(db, client, "a@example.com", "admin")
    return {"anon": {}, "seeker": sh, "recruiter": rh, "admin": ah}


def _call(client, key: str, headers: dict):
    method, path = key.split(" ", 1)
    path = re.sub(r"\{slug\}", "no-such-company", path)
    path = re.sub(r"\{task_id\}", "no-such-task", path)
    path = re.sub(r"\{\w+\}", "999999", path)
    kwargs = {"headers": headers}
    if method in ("POST", "PUT", "PATCH"):
        kwargs["json"] = {}
    return client.request(method, path, **kwargs)


@pytest.mark.parametrize("key", sorted(ACCESS))
def test_role_guards(client, identities, key):
    allowed = ALLOWED[ACCESS[key]]
    for who, headers in identities.items():
        status = _call(client, key, headers).status_code
        if who in allowed:
            assert status not in (401, 403), f"{who} was refused {key}"
        elif who == "anon":
            assert status == 401, f"anonymous got {status} on {key}"
        else:
            assert status == 403, f"{who} got {status} on {key}"


def test_no_access_to_another_account_resources(client, db):
    """Another recruiter or seeker gets 403/404 on everything that belongs to someone else."""
    rec_a, rah = auth_headers(db, client, "a@example.com", "recruiter", company="A Co")
    _, rbh = auth_headers(db, client, "b@example.com", "recruiter", company="B Co")
    owner, sh = auth_headers(db, client, "owner@example.com")
    _, other = auth_headers(db, client, "other@example.com")
    job = make_job(db, rec_a, title="Python Developer")
    rid = give_resume(client, sh)
    app_id = client.post("/api/applications", json={"job_id": job.id}, headers=sh).json()["id"]
    for to in ("shortlisted", "interview"):
        client.patch(
            f"/api/recruiter/applications/{app_id}/status", json={"status": to}, headers=rah
        )
    iv = client.post(
        f"/api/recruiter/applications/{app_id}/interviews",
        json={"starts_at": "2099-01-01T10:00:00+00:00", "mode": "video"},
        headers=rah,
    ).json()
    search = client.post(
        "/api/saved-searches", json={"name": "x", "params": {"q": "go"}}, headers=sh
    ).json()
    task = db.scalar(select(BackgroundTask).where(BackgroundTask.user_id == owner.id))

    attempts = {
        "recruiter B": (
            rbh,
            [
                ("GET", f"/api/recruiter/jobs/{job.id}", None),
                ("PATCH", f"/api/recruiter/jobs/{job.id}", {"title": "Hacked"}),
                ("POST", f"/api/recruiter/jobs/{job.id}/close", None),
                ("GET", f"/api/recruiter/jobs/{job.id}/applications", None),
                ("GET", f"/api/recruiter/analytics?job_id={job.id}", None),
                ("GET", f"/api/recruiter/stats/applications-weekly?job_id={job.id}", None),
                ("PATCH", f"/api/recruiter/applications/{app_id}/status", {"status": "offer"}),
                (
                    "POST",
                    f"/api/recruiter/applications/{app_id}/interviews",
                    {"starts_at": "2099-01-02T10:00:00+00:00", "mode": "phone"},
                ),
                ("PATCH", f"/api/recruiter/interviews/{iv['id']}", {"mode": "phone"}),
                ("POST", f"/api/recruiter/interviews/{iv['id']}/cancel", None),
                ("GET", f"/api/interviews/{iv['id']}/ics", None),
                ("GET", f"/api/applications/{app_id}", None),
                ("POST", f"/api/resumes/{rid}/link", None),
                ("GET", f"/api/tasks/{task.id}", None),
            ],
        ),
        "another seeker": (
            other,
            [
                ("GET", f"/api/resumes/{rid}", None),
                ("PUT", f"/api/resumes/{rid}", {"skills": []}),
                ("DELETE", f"/api/resumes/{rid}", None),
                ("POST", f"/api/resumes/{rid}/link", None),
                ("GET", f"/api/applications/{app_id}", None),
                ("GET", f"/api/interviews/{iv['id']}/ics", None),
                ("PATCH", f"/api/saved-searches/{search['id']}", {"alerts_enabled": False}),
                ("DELETE", f"/api/saved-searches/{search['id']}", None),
                ("GET", f"/api/tasks/{task.id}", None),
            ],
        ),
    }
    for who, (headers, calls) in attempts.items():
        for method, path, body in calls:
            res = client.request(method, path, headers=headers, json=body)
            assert res.status_code in (403, 404), f"{who}: {method} {path} -> {res.status_code}"
    # Nothing changed.
    assert client.get(f"/api/recruiter/jobs/{job.id}", headers=rah).json()["title"] != "Hacked"
    assert db.get(Resume, rid) is not None
    assert client.get("/api/interviews", headers=sh).json()[0]["status"] == "scheduled"


# ---------- CSRF ----------


def test_cookie_endpoints_require_the_csrf_header(client, db):
    from tests.factories import PASSWORD, make_user

    make_user(db, "s@example.com")
    body = {"email": "s@example.com", "password": PASSWORD}
    no_header = {"X-CSRF-Protection": ""}
    assert client.post("/api/auth/login", json=body, headers=no_header).status_code == 403
    assert client.post("/api/auth/login", json=body).status_code == 200
    assert client.post("/api/auth/refresh", headers=no_header).status_code == 403
    assert client.post("/api/auth/logout", headers=no_header).status_code == 403
    evil = client.post("/api/auth/refresh", headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403 and "origin" in evil.json()["detail"]
    ok = client.post("/api/auth/refresh", headers={"Origin": "http://localhost:8080"})
    assert ok.status_code == 200


# ---------- security headers ----------


def test_security_headers_on_api_responses(client, monkeypatch):
    res = client.get("/api/jobs")
    h = res.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in h["permissions-policy"]
    assert "strict-transport-security" not in h  # plain HTTP in dev
    assert "content-security-policy" not in client.get("/api/docs").headers
    login = client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"})
    assert login.headers["cache-control"] == "no-store"
    monkeypatch.setattr(settings, "cookie_secure", True)
    assert "max-age=31536000" in client.get("/api/jobs").headers["strict-transport-security"]


# ---------- upload / download ----------


def test_hostile_filenames_are_neutralised(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    for name in ["..\\..\\etc\\passwd.pdf", '"; evil="x.pdf', "cv\r\nX-Injected: 1.pdf"]:
        res = post_resume(client, h, name, PDF, PDF_MIME)
        assert res.status_code == 202, name
        stored = res.json()["original_filename"]
        assert not any(c in stored for c in '\\/"\r\n;'), stored
        file = fetch_resume_file(client, h, res.json()["id"])
        assert "x-injected" not in file.headers
        assert file.headers["content-disposition"].count('"') == 2
    key = db.scalar(select(Resume.storage_key))
    assert re.fullmatch(r"resumes/\d+/[0-9a-f]{32}\.pdf", key)  # never derived from the name


def test_html_disguised_as_pdf_is_served_inert(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    polyglot = PDF + b"<html><script>alert(document.cookie)</script></html>"
    rid = post_resume(client, h, "cv.pdf", polyglot, PDF_MIME).json()["id"]
    file = fetch_resume_file(client, h, rid)
    assert file.headers["content-type"] == "application/pdf"
    assert file.headers["x-content-type-options"] == "nosniff"
    assert file.headers["content-disposition"].startswith("inline;")


def test_signed_link_cannot_be_moved_to_another_resume(client, db):
    _, h = auth_headers(db, client, "a@example.com")
    _, h2 = auth_headers(db, client, "b@example.com")
    mine = post_resume(client, h, "a.pdf", PDF, PDF_MIME).json()["id"]
    theirs = post_resume(client, h2, "b.pdf", PDF, PDF_MIME).json()["id"]
    url = client.post(f"/api/resumes/{mine}/link", headers=h).json()["url"]
    moved = url.replace(f"/resumes/{mine}?", f"/resumes/{theirs}?")
    assert client.get(moved).status_code == 403
    assert client.get(url.replace("exp=", "exp=9")).status_code == 403  # extended expiry
