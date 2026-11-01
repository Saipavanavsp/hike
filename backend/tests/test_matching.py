from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import func, select

from app.models import MatchScore, SeekerProfile
from app.models.enums import RemoteType, RoleCategory
from app.services import matching
from app.services.matching import (
    JobSide,
    ResumeSide,
    compute_match,
    experience_fit,
    location_fit,
    semantic_component,
    skill_overlap,
)
from app.services.resume_parser import PDF_MIME
from tests.factories import auth_headers, make_user, post_resume
from tests.test_jobs_api import make_job

FIXTURES = Path(__file__).parent / "fixtures"


def unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def resume(**kw):
    d = dict(
        vector=unit([1, 0]),
        skills=["Python", "Django"],
        years=2.0,
        locations={"hyderabad"},
        open_to_remote=True,
    )
    d.update(kw)
    return ResumeSide(**d)


def job(**kw):
    d = dict(
        vector=unit([1, 0]),
        skills=["Python", "Django", "Redis"],
        experience_min=1,
        experience_max=3,
        location="Hyderabad",
        remote_type="hybrid",
    )
    d.update(kw)
    return JobSide(**d)


# ---------- pure functions ----------


def test_semantic_rescaling():
    assert semantic_component(matching.SEM_FLOOR) == 0
    assert semantic_component(matching.SEM_CEIL) == 1
    assert semantic_component(-0.3) == 0 and semantic_component(0.95) == 1
    mid = (matching.SEM_FLOOR + matching.SEM_CEIL) / 2
    assert semantic_component(mid) == pytest.approx(0.5)


def test_skill_overlap_uses_aliases():
    matched, missing = skill_overlap(
        ["JS", "Postgres", "Docker"], ["JavaScript", "PostgreSQL", "AWS"]
    )
    assert matched == ["JavaScript", "PostgreSQL"]
    assert missing == ["AWS"]


def test_experience_fit_rules():
    assert experience_fit(2, 1, 3) == (1.0, True)
    assert experience_fit(1, 1, 3) == (1.0, True)
    assert experience_fit(0.5, 1, 3) == (0.75, False)
    assert experience_fit(0, 3, 5) == (0.0, False)
    assert experience_fit(5, 1, 3)[0] == pytest.approx(0.8)
    assert experience_fit(20, 1, 3) == (0.6, False)
    assert experience_fit(None, 1, 3) == (0.5, False)


def test_location_fit_rules():
    assert location_fit(resume(), job()) == (1.0, True)
    assert location_fit(resume(), job(location="Pune")) == (0.0, False)
    assert location_fit(resume(open_to_remote=False), job(remote_type="remote")) == (0.0, False)
    assert location_fit(resume(), job(remote_type="remote", location="Remote")) == (1.0, True)
    assert location_fit(resume(locations=set()), job(location="Pune")) == (1.0, True)


def test_compute_match_perfect_and_weighted():
    b = compute_match(resume(skills=["Python", "Django", "Redis"]), job())
    assert b["score"] == 100
    assert b["skills_ratio"] == "3/3" and b["skills_missing"] == []

    # Orthogonal vectors, 2/3 skills, in range, right city.
    b = compute_match(resume(vector=unit([0, 1])), job())
    expected = 100 * (0.5 * 0 + 0.35 * (2 / 3) + 0.10 * 1 + 0.05 * 1)
    assert b["score"] == round(expected)
    assert b["skills_matched"] == ["Python", "Django"] and b["skills_missing"] == ["Redis"]
    assert b["experience_ok"] and b["location_ok"]


def test_job_without_skills_counts_as_full_overlap():
    b = compute_match(resume(), job(skills=[]))
    assert b["skill_overlap"] == 1.0 and b["skills_ratio"] == "0/0"


def test_weights_sum_to_one():
    total = matching.W_SEMANTIC + matching.W_SKILLS + matching.W_EXPERIENCE + matching.W_LOCATION
    assert total == pytest.approx(1.0)


# ---------- end to end through the API ----------


def seeker_with_resume(client, db, email="priya@example.com"):
    user, h = auth_headers(db, client, email)
    data = (FIXTURES / "priya_sharma_backend.pdf").read_bytes()
    rid = post_resume(client, h, "cv.pdf", data, PDF_MIME).json()["id"]
    res = client.put(
        f"/api/resumes/{rid}",
        json={
            "skills": ["Python", "Django", "FastAPI", "PostgreSQL", "Redis", "Docker"],
            "years_experience": 3,
        },
        headers=h,
    )
    assert res.json()["predicted_category"] == "backend"
    return user, h


def test_confirmed_resume_gets_scores_and_breakdown(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    good = make_job(
        db,
        rec,
        title="Python Backend Engineer",
        skills=["Python", "Django", "PostgreSQL", "Kafka"],
        location="Hyderabad",
        experience_min=2,
        experience_max=4,
    )
    bad = make_job(
        db,
        rec,
        title="iOS Developer",
        role_category=RoleCategory.mobile,
        skills=["Swift", "SwiftUI", "Xcode"],
        description_md="## About the role\nBuild our iPhone app in Swift and SwiftUI. Ship to the App Store.",
        location="Chennai",
        experience_min=5,
        experience_max=8,
    )
    _, h = seeker_with_resume(client, db)

    detail = client.get(f"/api/jobs/{good.id}", headers=h).json()
    m = detail["match"]
    assert m["skills_ratio"] == "3/4"
    assert m["skills_missing"] == ["Kafka"]
    assert m["experience_ok"] is True and m["location_ok"] is True
    assert detail["match_score"] == m["score"]

    bad_detail = client.get(f"/api/jobs/{bad.id}", headers=h).json()
    assert bad_detail["match"]["score"] < m["score"]
    assert bad_detail["match"]["location_ok"] is False

    listing = client.get("/api/jobs", params={"sort": "match"}, headers=h).json()
    assert [j["id"] for j in listing["items"]] == [good.id, bad.id]
    assert all(j["match_score"] is not None for j in listing["items"])

    # Anonymous users and seekers without a resume get no match data.
    assert client.get(f"/api/jobs/{good.id}").json()["match"] is None
    _, h2 = auth_headers(db, client, "noresume@example.com")
    assert client.get("/api/jobs", headers=h2).json()["items"][0]["match_score"] is None


def test_match_cache_reused_and_invalidated(client, db):
    rec, rh = auth_headers(db, client, "rec@example.com", "recruiter")
    j = make_job(db, rec, skills=["Python", "Kafka"])
    user, h = seeker_with_resume(client, db)

    first = client.get(f"/api/jobs/{j.id}", headers=h).json()["match"]
    count = db.scalar(select(func.count()).select_from(MatchScore))
    assert count == 1
    row = db.scalar(select(MatchScore))
    computed_at = row.computed_at

    # Same inputs: served from cache.
    assert client.get(f"/api/jobs/{j.id}", headers=h).json()["match"] == first
    db.expire_all()
    assert db.scalar(select(MatchScore)).computed_at == computed_at

    # Job changes: recomputed.
    client.patch(f"/api/recruiter/jobs/{j.id}", json={"skills": ["Python", "Redis"]}, headers=rh)
    second = client.get(f"/api/jobs/{j.id}", headers=h).json()["match"]
    assert second["skills_ratio"] == "2/2"

    # Profile location change also invalidates.
    profile = db.get(SeekerProfile, user.id)
    profile.current_location = "Pune"
    profile.preferred_locations = []
    db.commit()
    third = client.get(f"/api/jobs/{j.id}", headers=h).json()["match"]
    assert third["location_ok"] is False


def test_remote_job_location(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    j = make_job(db, rec, location="Remote", remote_type=RemoteType.remote)
    _, h = seeker_with_resume(client, db)
    assert client.get(f"/api/jobs/{j.id}", headers=h).json()["match"]["location_ok"] is True


def test_job_embedding_stored_on_create(client, db):
    from app.models import Job

    _, h = auth_headers(db, client, "rec@example.com", "recruiter")
    from tests.test_jobs_api import job_payload

    jid = client.post("/api/recruiter/jobs", json=job_payload(), headers=h).json()["id"]
    job = db.get(Job, jid)
    assert job.embedding_hash is not None
    assert len(job.embedding) == 384
