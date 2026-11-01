import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models import Application
from app.models.enums import JobStatus
from app.services.resume_parser import PDF_MIME
from tests.factories import auth_headers, fetch_resume_file, login, make_user, post_resume
from tests.test_jobs_api import make_job

FIXTURES = Path(__file__).parent / "fixtures"


def give_resume(client, h, name="priya_sharma_backend.pdf"):
    data = (FIXTURES / name).read_bytes()
    rid = post_resume(client, h, name, data, PDF_MIME).json()["id"]
    client.put(f"/api/resumes/{rid}", json={"skills": ["Python", "Django"]}, headers=h)
    return rid


@pytest.fixture
def setup(client, db):
    rec, rh = auth_headers(db, client, "rec@example.com", "recruiter")
    other_rec, orh = auth_headers(db, client, "other@example.com", "recruiter", company="Other Co")
    job = make_job(db, rec, title="Python Developer")
    other_job = make_job(db, other_rec, title="Other Job")
    seeker, sh = auth_headers(db, client, "priya@example.com", full_name="Priya Sharma")
    give_resume(client, sh)
    return dict(rec=rec, rh=rh, orh=orh, job=job, other_job=other_job, seeker=seeker, sh=sh)


def apply(client, h, job_id, note=None):
    return client.post("/api/applications", json={"job_id": job_id, "note": note}, headers=h)


def move(client, h, app_id, status):
    return client.patch(
        f"/api/recruiter/applications/{app_id}/status", json={"status": status}, headers=h
    )


def test_apply_creates_application_history_and_notification(client, setup, caplog):
    s = setup
    with caplog.at_level(logging.INFO, logger="hike.email"):
        res = apply(client, s["sh"], s["job"].id, "  Available to join in 30 days.  ")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "applied"
    assert body["note"] == "Available to join in 30 days."
    assert [h["to_status"] for h in body["history"]] == ["applied"]
    assert "[email] to=rec@example.com" in caplog.text

    notes = client.get("/api/notifications", headers=s["rh"]).json()
    assert notes["unread"] == 1
    assert "Priya Sharma" in notes["items"][0]["title"]

    detail = client.get(f"/api/jobs/{s['job'].id}", headers=s["sh"]).json()
    assert detail["application_status"] == "applied"


def test_duplicate_apply_blocked(client, setup):
    s = setup
    assert apply(client, s["sh"], s["job"].id).status_code == 201
    res = apply(client, s["sh"], s["job"].id)
    assert res.status_code == 409
    assert res.json()["detail"] == "You have already applied to this job"
    assert len(client.get("/api/applications", headers=s["sh"]).json()) == 1


def test_apply_requires_resume_open_job_and_seeker_role(client, db, setup):
    s = setup
    _, no_resume = auth_headers(db, client, "new@example.com")
    assert apply(client, no_resume, s["job"].id).status_code == 422
    closed = make_job(db, s["rec"], status=JobStatus.closed)
    assert apply(client, s["sh"], closed.id).status_code == 409
    assert apply(client, s["sh"], 99999).status_code == 404
    assert apply(client, s["rh"], s["job"].id).status_code == 403


def test_recruiter_moves_candidate_and_seeker_sees_timeline(client, setup):
    s = setup
    app_id = apply(client, s["sh"], s["job"].id).json()["id"]

    res = move(client, s["rh"], app_id, "shortlisted")
    assert res.status_code == 200
    assert res.json()["status"] == "shortlisted"
    move(client, s["rh"], app_id, "interview")

    mine = client.get("/api/applications", headers=s["sh"]).json()[0]
    assert mine["status"] == "interview"
    timeline = [(h["from_status"], h["to_status"]) for h in mine["history"]]
    assert timeline == [(None, "applied"), ("applied", "shortlisted"), ("shortlisted", "interview")]
    assert mine["history"][1]["changed_by_role"] == "recruiter"

    notes = client.get("/api/notifications", headers=s["sh"]).json()
    assert notes["unread"] == 2
    assert notes["items"][0]["title"].endswith(": Interview")


def test_seeker_cannot_change_status(client, setup):
    s = setup
    app_id = apply(client, s["sh"], s["job"].id).json()["id"]
    assert move(client, s["sh"], app_id, "offer").status_code == 403


def test_recruiter_can_only_manage_own_jobs(client, setup):
    s = setup
    app_id = apply(client, s["sh"], s["job"].id).json()["id"]
    assert move(client, s["orh"], app_id, "shortlisted").status_code == 403
    assert (
        client.get(f"/api/recruiter/jobs/{s['job'].id}/applications", headers=s["orh"]).status_code
        == 403
    )
    assert client.get(f"/api/applications/{app_id}", headers=s["orh"]).status_code == 404
    rid = client.get("/api/applications", headers=s["sh"]).json()[0]["id"]
    assert rid == app_id


def test_invalid_transition_rejected(client, setup):
    s = setup
    app_id = apply(client, s["sh"], s["job"].id).json()["id"]
    res = move(client, s["rh"], app_id, "offer")
    assert res.status_code == 422
    assert res.json()["detail"] == "Cannot move from Applied to Offer"
    assert move(client, s["rh"], app_id, "rejected").status_code == 200
    assert move(client, s["rh"], app_id, "shortlisted").status_code == 200  # reconsidered
    # Same status is a no-op, not an error, and adds no history row.
    assert move(client, s["rh"], app_id, "shortlisted").status_code == 200
    mine = client.get("/api/applications", headers=s["sh"]).json()[0]
    assert len(mine["history"]) == 3


def test_recruiter_candidate_list_ranked_with_match_and_phone(client, db, setup):
    s = setup
    apply(client, s["sh"], s["job"].id)
    seeker2, h2 = auth_headers(db, client, "kavya@example.com")
    give_resume(client, h2, "kavya_iyer_data.pdf")
    apply(client, h2, s["job"].id)

    res = client.get(f"/api/recruiter/jobs/{s['job'].id}/applications", headers=s["rh"])
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 2
    scores = [r["match"]["score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    priya = next(r for r in rows if r["candidate"]["email"] == "priya@example.com")
    assert priya["candidate"]["phone"] == "+919876543210"
    assert priya["resume"]["predicted_category"] == "backend"

    filtered = client.get(
        f"/api/recruiter/jobs/{s['job'].id}/applications",
        params={"status": "applied", "category": "data_ml"},
        headers=s["rh"],
    ).json()
    assert [r["candidate"]["email"] for r in filtered] == ["kavya@example.com"]

    counts = {j["id"]: j for j in client.get("/api/recruiter/jobs", headers=s["rh"]).json()}
    assert counts[s["job"].id]["applications_count"] == 2
    assert counts[s["job"].id]["new_count"] == 2


def test_recruiter_can_open_applicant_resume_but_not_others(client, db, setup):
    s = setup
    apply(client, s["sh"], s["job"].id)
    rows = client.get(f"/api/recruiter/jobs/{s['job'].id}/applications", headers=s["rh"]).json()
    rid = rows[0]["resume"]["id"]
    assert fetch_resume_file(client, s["rh"], rid).status_code == 200
    assert fetch_resume_file(client, s["orh"], rid).status_code == 404


def test_phone_never_exposed_to_other_seekers(client, db, setup):
    s = setup
    app_id = apply(client, s["sh"], s["job"].id).json()["id"]
    _, h2 = auth_headers(db, client, "nosy@example.com")
    assert client.get(f"/api/applications/{app_id}", headers=h2).status_code == 404
    for url in ["/api/jobs", f"/api/jobs/{s['job'].id}", "/api/applications"]:
        assert "+919876543210" not in client.get(url, headers=h2).text


def test_weekly_counts_zero_filled(client, db, setup):
    s = setup
    app_id = apply(client, s["sh"], s["job"].id).json()["id"]
    a = db.get(Application, app_id)
    a.applied_at = datetime.now(UTC) - timedelta(days=2)
    db.commit()
    seeker2, h2 = auth_headers(db, client, "b@example.com")
    give_resume(client, h2)
    apply(client, h2, s["job"].id)

    days = client.get("/api/recruiter/stats/applications-weekly", headers=s["rh"]).json()
    assert len(days) == 7
    assert sum(d["count"] for d in days) == 2
    assert days[-1]["count"] == 1 and days[-3]["count"] == 1
    other = client.get("/api/recruiter/stats/applications-weekly", headers=s["orh"]).json()
    assert sum(d["count"] for d in other) == 0
    res = client.get(
        "/api/recruiter/stats/applications-weekly",
        params={"job_id": s["job"].id},
        headers=s["orh"],
    )
    assert res.status_code == 403


def test_notifications_mark_read(client, setup):
    s = setup
    app_id = apply(client, s["sh"], s["job"].id).json()["id"]
    items = client.get("/api/notifications", headers=s["rh"]).json()["items"]
    nid = items[0]["id"]
    assert client.post(f"/api/notifications/{nid}/read", headers=s["sh"]).status_code == 404
    assert client.post(f"/api/notifications/{nid}/read", headers=s["rh"]).status_code == 204
    assert client.get("/api/notifications", headers=s["rh"]).json()["unread"] == 0
    move(client, s["rh"], app_id, "shortlisted")
    assert client.post("/api/notifications/read-all", headers=s["sh"]).status_code == 204
    assert client.get("/api/notifications", headers=s["sh"]).json()["unread"] == 0


def test_admin_can_manage_any_application(client, db, setup):
    s = setup
    app_id = apply(client, s["sh"], s["job"].id).json()["id"]
    make_user(db, "admin@example.com", "admin")
    admin = login(client, "admin@example.com")
    assert move(client, admin, app_id, "shortlisted").status_code == 200
    assert (
        client.get(f"/api/applications/{app_id}", headers=admin).json()["status"] == "shortlisted"
    )
