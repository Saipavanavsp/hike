"""Score explanations, identity redaction, interviews + calendar, email, saved-search alerts,
recruiter analytics, company profiles, audit log and email preferences."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.ml.embeddings import content_hash
from app.models import (
    Application,
    ApplicationStatusHistory,
    AuditLog,
    Interview,
    Notification,
    Resume,
    SavedSearch,
)
from app.models.enums import ApplicationStatus
from app.services import calendar, email, redaction
from app.services.matching import ensure_resume_derived, resume_matching_text
from tests.factories import auth_headers, login, make_user
from tests.test_applications import give_resume
from tests.test_jobs_api import make_job

S = ApplicationStatus


def future(hours: int = 48) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).replace(microsecond=0).isoformat()


@pytest.fixture
def pipeline(client, db):
    """A recruiter's job with one seeker's application moved to the Interview stage."""
    rec, rh = auth_headers(db, client, "rec@example.com", "recruiter", company="Lumen Test Co")
    _, orh = auth_headers(db, client, "other@example.com", "recruiter", company="Other Co")
    job = make_job(db, rec, title="Python Developer")
    seeker, sh = auth_headers(db, client, "seeker@example.com", full_name="Asha Rao")
    give_resume(client, sh)
    app_id = client.post("/api/applications", json={"job_id": job.id}, headers=sh).json()["id"]
    for to in ("shortlisted", "interview"):
        res = client.patch(
            f"/api/recruiter/applications/{app_id}/status", json={"status": to}, headers=rh
        )
        assert res.status_code == 200, res.text
    return {"job": job, "rh": rh, "orh": orh, "sh": sh, "app_id": app_id, "seeker": seeker}


# ---------- explainable scores ----------


def test_breakdown_lists_every_component_with_points(client, pipeline):
    p = pipeline
    detail = client.get(f"/api/jobs/{p['job'].id}", headers=p["sh"]).json()
    m = detail["match"]
    keys = [c["key"] for c in m["components"]]
    assert keys == ["semantic", "skills", "experience", "location"]
    assert [c["weight"] for c in m["components"]] == [50, 35, 10, 5]
    total = sum(c["points"] for c in m["components"])
    assert abs(total - m["score"]) <= 0.6
    for c in m["components"]:
        assert 0 <= c["points"] <= c["weight"]
        assert c["detail"]
    # Recruiters get the same breakdown.
    rows = client.get(f"/api/recruiter/jobs/{p['job'].id}/applications", headers=p["rh"]).json()
    assert [c["key"] for c in rows[0]["match"]["components"]] == keys


# ---------- identity redaction ----------


def test_redaction_removes_identity_but_keeps_content():
    text = (
        "Asha Rao\nasha.rao@example.com | +91 98765 43210 | linkedin.com/in/asharao\n"
        "Python developer with Django and PostgreSQL.\n"
        "B.Tech, Apex National Institute of Technology, 2021\n"
        "Studied at Lakeside College."
    )
    out = redaction.redact_identity(text, ["Asha Rao", None])
    for leaked in ("Asha", "Rao", "example.com", "98765", "linkedin", "Apex", "Lakeside"):
        assert leaked.lower() not in out.lower(), leaked
    assert "Python developer with Django and PostgreSQL" in out
    assert "B.Tech" in out and "2021" in out


def test_embedding_uses_redacted_text(client, db):
    user, h = auth_headers(db, client, "asha@example.com", full_name="Asha Rao")
    rid = give_resume(client, h)
    resume = db.get(Resume, rid)
    db.refresh(resume)
    redacted = resume_matching_text(resume, "Asha Rao")
    assert "Asha" not in redacted
    ensure_resume_derived(db, resume)
    assert resume.embedding_hash == content_hash(redacted)


# ---------- interviews + calendar ----------


def test_schedule_interview_notifies_with_calendar_invite(client, db, pipeline, caplog):
    p = pipeline
    body = {
        "starts_at": future(),
        "duration_minutes": 45,
        "mode": "video",
        "location": "https://meet.example.com/abc",
        "notes": "Bring a laptop, please",
    }
    with caplog.at_level(logging.INFO, logger="hike.email"):
        res = client.post(
            f"/api/recruiter/applications/{p['app_id']}/interviews", json=body, headers=p["rh"]
        )
    assert res.status_code == 201, res.text
    iv = res.json()
    assert iv["status"] == "scheduled" and iv["candidate_name"] == "Asha Rao"
    assert iv["google_calendar_url"].startswith("https://calendar.google.com/calendar/render?")
    n = db.scalar(select(Notification).where(Notification.type == "interview_scheduled"))
    assert n.user_id == p["seeker"].id and n.payload["interview_id"] == iv["id"]
    sent = [r for r in caplog.records if "to=seeker@example.com" in r.getMessage()]
    assert sent and sent[-1].attachments == ["interview.ics"]

    # Seeker sees it and can download the .ics; another recruiter cannot.
    mine = client.get("/api/interviews", params={"upcoming": True}, headers=p["sh"]).json()
    assert [i["id"] for i in mine] == [iv["id"]]
    ics = client.get(f"/api/interviews/{iv['id']}/ics", headers=p["sh"])
    assert ics.status_code == 200
    assert ics.headers["content-type"].startswith("text/calendar")
    text = ics.text.replace("\r\n ", "")  # unfold long lines
    assert f"UID:interview-{iv['id']}@hike" in text
    assert "SEQUENCE:0" in text and "STATUS:CONFIRMED" in text and "METHOD:REQUEST" in text
    assert "Bring a laptop\\, please" in text  # commas escaped
    assert client.get(f"/api/interviews/{iv['id']}/ics", headers=p["orh"]).status_code == 404
    assert client.get("/api/interviews", headers=p["orh"]).json() == []


def test_interview_rules_reschedule_and_cancel(client, db, pipeline):
    p = pipeline
    url = f"/api/recruiter/applications/{p['app_id']}/interviews"
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert (
        client.post(url, json={"starts_at": past, "mode": "phone"}, headers=p["rh"]).status_code
        == 422
    )
    assert (
        client.post(
            url, json={"starts_at": future(), "mode": "teleport"}, headers=p["rh"]
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, json={"starts_at": future(), "mode": "phone"}, headers=p["orh"]
        ).status_code
        == 403
    )
    assert (
        client.post(url, json={"starts_at": future(), "mode": "phone"}, headers=p["sh"]).status_code
        == 403
    )

    iv = client.post(url, json={"starts_at": future(), "mode": "phone"}, headers=p["rh"]).json()
    res = client.patch(
        f"/api/recruiter/interviews/{iv['id']}",
        json={"starts_at": future(72), "mode": "onsite", "location": "HITEC City office"},
        headers=p["rh"],
    )
    assert res.status_code == 200
    row = db.get(Interview, iv["id"])
    db.refresh(row)
    assert row.sequence == 1 and row.mode == "onsite"

    res = client.post(f"/api/recruiter/interviews/{iv['id']}/cancel", headers=p["rh"])
    assert res.json()["status"] == "cancelled"
    ics = client.get(f"/api/interviews/{iv['id']}/ics", headers=p["sh"]).text
    assert "STATUS:CANCELLED" in ics and "SEQUENCE:2" in ics and "METHOD:CANCEL" in ics
    kinds = [
        n.type
        for n in db.scalars(select(Notification).where(Notification.user_id == p["seeker"].id))
    ]
    assert {"interview_scheduled", "interview_rescheduled", "interview_cancelled"} <= set(kinds)
    assert (
        client.patch(
            f"/api/recruiter/interviews/{iv['id']}", json={"mode": "video"}, headers=p["rh"]
        ).status_code
        == 409
    )


def test_interview_requires_interview_stage(client, db, pipeline):
    p = pipeline
    client.patch(
        f"/api/recruiter/applications/{p['app_id']}/status",
        json={"status": "shortlisted"},
        headers=p["rh"],
    )
    res = client.post(
        f"/api/recruiter/applications/{p['app_id']}/interviews",
        json={"starts_at": future(), "mode": "video"},
        headers=p["rh"],
    )
    assert res.status_code == 409


def test_ics_lines_are_folded_to_75_octets():
    line = "DESCRIPTION:" + "é" * 80
    folded = calendar._fold(line)
    for part in folded.split("\r\n"):
        assert len(part.encode("utf-8")) <= 75
    assert folded.replace("\r\n ", "") == line


# ---------- email ----------


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        self.user = user

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_smtp_backend_sends_with_ics_attachment(client, db, pipeline, monkeypatch):
    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    p = pipeline
    client.post(
        f"/api/recruiter/applications/{p['app_id']}/interviews",
        json={"starts_at": future(), "mode": "video"},
        headers=p["rh"],
    )
    msg = FakeSMTP.sent[-1]
    assert msg["To"] == "seeker@example.com"
    assert msg["Subject"].startswith("Interview scheduled: Python Developer")
    parts = [part for part in msg.iter_attachments()]
    assert parts[0].get_filename() == "interview.ics"
    assert parts[0].get_content_type() == "text/calendar"
    assert "BEGIN:VCALENDAR" in parts[0].get_content()


def test_email_preference_opt_out(client, db, pipeline):
    p = pipeline
    assert client.get("/api/account/preferences", headers=p["sh"]).json() == {
        "email_notifications": True
    }
    res = client.put(
        "/api/account/preferences", json={"email_notifications": False}, headers=p["sh"]
    )
    assert res.json() == {"email_notifications": False}
    client.patch(
        f"/api/recruiter/applications/{p['app_id']}/status",
        json={"status": "offer"},
        headers=p["rh"],
    )
    n = db.scalar(
        select(Notification)
        .where(Notification.user_id == p["seeker"].id, Notification.type == "status_changed")
        .order_by(Notification.id.desc())
    )
    db.refresh(n)
    assert n.emailed_at is None  # in-app only


# ---------- saved searches + alerts ----------


def test_saved_search_crud_and_ownership(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    _, other = auth_headers(db, client, "o@example.com")
    body = {"name": "Python in Pune", "params": {"q": "python", "location": ["Pune"]}}
    created = client.post("/api/saved-searches", json=body, headers=h)
    assert created.status_code == 201
    s = created.json()
    assert s["summary"] == '"python" · Pune' and s["alerts_enabled"] is True
    assert client.get("/api/saved-searches", headers=other).json() == []
    assert client.delete(f"/api/saved-searches/{s['id']}", headers=other).status_code == 404
    res = client.patch(f"/api/saved-searches/{s['id']}", json={"alerts_enabled": False}, headers=h)
    assert res.json()["alerts_enabled"] is False
    assert client.delete(f"/api/saved-searches/{s['id']}", headers=h).status_code == 204
    bad = {"name": "x", "params": {"role": ["astronaut"]}}
    assert client.post("/api/saved-searches", json=bad, headers=h).status_code == 422
    _, rh = auth_headers(db, client, "r@example.com", "recruiter")
    assert client.get("/api/saved-searches", headers=rh).status_code == 403


def test_new_job_alerts_matching_saved_searches(client, db):
    rec, rh = auth_headers(db, client, "rec@example.com", "recruiter")
    match_user, mh = auth_headers(db, client, "match@example.com")
    miss_user, xh = auth_headers(db, client, "miss@example.com")
    off_user, oh = auth_headers(db, client, "off@example.com")
    client.post(
        "/api/saved-searches", json={"name": "Go jobs", "params": {"q": "golang"}}, headers=mh
    )
    client.post(
        "/api/saved-searches", json={"name": "Data", "params": {"role": ["data_ml"]}}, headers=xh
    )
    client.post(
        "/api/saved-searches",
        json={"name": "Go too", "params": {"q": "golang"}, "alerts_enabled": False},
        headers=oh,
    )
    job = {
        "title": "Golang Backend Engineer",
        "company_name": "Deltawave Test",
        "role_category": "backend",
        "location": "Pune",
        "remote_type": "hybrid",
        "experience_min": 2,
        "experience_max": 5,
        "salary_min": 1500000,
        "salary_max": 2500000,
        "skills": ["Go", "PostgreSQL"],
        "description_md": "Build golang services for our logistics platform. " * 3,
    }
    res = client.post("/api/recruiter/jobs", json=job, headers=rh)
    assert res.status_code == 201, res.text
    alerts = list(db.scalars(select(Notification).where(Notification.type == "saved_search_match")))
    assert [a.user_id for a in alerts] == [match_user.id]
    assert alerts[0].link == f"/jobs/{res.json()['id']}"
    s = db.scalar(select(SavedSearch).where(SavedSearch.user_id == match_user.id))
    db.refresh(s)
    assert s.last_alert_at is not None
    assert miss_user and off_user


# ---------- analytics ----------


def test_recruiter_analytics_funnel_and_timing(client, db):
    rec, rh = auth_headers(db, client, "rec@example.com", "recruiter")
    _, orh = auth_headers(db, client, "other@example.com", "recruiter", company="Other Co")
    job = make_job(db, rec, title="Python Developer")
    t0 = datetime(2026, 10, 1, tzinfo=UTC)
    paths = [
        [S.applied],
        [S.applied, S.shortlisted],
        [S.applied, S.shortlisted, S.interview, S.rejected],
        [S.applied, S.shortlisted, S.interview, S.offer],
    ]
    for i, path in enumerate(paths):
        seeker = make_user(db, f"s{i}@example.com")
        give_resume(client, login(client, seeker.email))
        resume_id = db.scalar(select(Resume.id).where(Resume.user_id == seeker.id))
        app = Application(
            job_id=job.id, seeker_id=seeker.id, resume_id=resume_id, status=path[-1], applied_at=t0
        )
        db.add(app)
        db.flush()
        prev = None
        for step, status in enumerate(path):
            db.add(
                ApplicationStatusHistory(
                    application_id=app.id,
                    from_status=prev,
                    to_status=status,
                    changed_at=t0 + timedelta(days=2 * step),
                )
            )
            prev = status
    db.commit()

    a = client.get("/api/recruiter/analytics", headers=rh).json()
    assert a["total_applications"] == 4
    assert [(f["stage"], f["count"]) for f in a["funnel"]] == [
        ("applied", 4),
        ("shortlisted", 3),
        ("interview", 2),
        ("offer", 1),
    ]
    assert a["funnel"][1]["conversion_from_previous"] == 0.75
    assert a["funnel"][3]["conversion_from_previous"] == 0.5
    assert a["rejected"] == 1 and a["offer_rate"] == 0.25
    assert a["median_days_to_first_response"] == 2.0
    assert a["median_days_to_offer"] == 6.0
    assert a["avg_days_in_stage"]["applied"] == 2.0
    assert a["by_job"][0]["offers"] == 1
    assert client.get("/api/recruiter/analytics", headers=orh).json()["total_applications"] == 0
    assert (
        client.get("/api/recruiter/analytics", params={"job_id": job.id}, headers=orh).status_code
        == 403
    )


# ---------- company profiles ----------


def test_company_profile_public_page_and_edit(client, db):
    rec, rh = auth_headers(db, client, "rec@example.com", "recruiter", company="Lumen Test Co")
    open_job = make_job(db, rec, title="Open Role")
    closed = make_job(db, rec, title="Closed Role")
    client.post(f"/api/recruiter/jobs/{closed.id}/close", headers=rh)
    slug = client.get("/api/recruiter/company", headers=rh).json()["slug"]

    res = client.put(
        "/api/recruiter/company",
        json={"website": "lumen.example", "about": "x"},
        headers=rh,
    )
    assert res.status_code == 422
    res = client.put(
        "/api/recruiter/company",
        json={
            "website": "https://lumen.example",
            "about": "We track shipments.",
            "hq_city": "Hyderabad",
        },
        headers=rh,
    )
    assert res.status_code == 200 and res.json()["about"] == "We track shipments."

    page = client.get(f"/api/companies/{slug}").json()  # public, no token
    assert page["company"]["website"] == "https://lumen.example"
    assert [j["title"] for j in page["open_jobs"]] == [open_job.title]
    assert page["recruiters"] == 1
    assert client.get("/api/companies/no-such-company").status_code == 404
    _, sh = auth_headers(db, client, "s@example.com")
    assert client.put("/api/recruiter/company", json={"about": "hi"}, headers=sh).status_code == 403


# ---------- audit log ----------


def test_audit_log_records_sensitive_actions(client, db, pipeline):
    from tests.factories import fetch_resume_file

    p = pipeline
    admin, ah = auth_headers(db, client, "admin@example.com", "admin")
    victim = make_user(db, "victim@example.com")
    client.post("/api/auth/login", json={"email": "victim@example.com", "password": "nope"})
    client.post(
        "/api/admin/users/deactivate",
        json={"ids": [victim.id]},
        headers={**ah, "X-Request-ID": "audit-req-1"},
    )
    rows = client.get(f"/api/recruiter/jobs/{p['job'].id}/applications", headers=p["rh"]).json()
    assert fetch_resume_file(client, p["rh"], rows[0]["resume"]["id"]).status_code == 200

    actions = {a.action for a in db.scalars(select(AuditLog))}
    assert {
        "auth.login",
        "auth.login_failed",
        "admin.users.deactivate",
        "application.status_change",
        "resume.file_access",
    } <= actions
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "admin.users.deactivate"))
    assert entry.actor_id == admin.id and entry.details["ids"] == [victim.id]
    assert entry.request_id == "audit-req-1" and entry.ip

    page = client.get("/api/admin/audit", params={"action": "admin."}, headers=ah).json()
    assert [i["action"] for i in page["items"]] == ["admin.users.deactivate"]
    assert page["items"][0]["actor"] == "Admin (admin@example.com)"
    assert client.get("/api/admin/audit", headers=p["rh"]).status_code == 403


def test_account_deletion_keeps_anonymous_audit_entry(client, db):
    from tests.factories import PASSWORD

    user, h = auth_headers(db, client, "gone@example.com")
    uid = user.id
    assert (
        client.post("/api/account/delete", json={"password": PASSWORD}, headers=h).status_code
        == 204
    )
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "account.delete"))
    assert entry.target_id == uid and entry.actor_id is None and entry.actor_role == "seeker"
