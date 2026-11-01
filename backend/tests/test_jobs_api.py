from datetime import UTC, datetime, timedelta

from app.models import Job
from app.models.enums import JobStatus, RemoteType, RoleCategory
from tests.factories import auth_headers, make_user

DESC = (
    "## About the role\nYou will build and run APIs used by thousands of customers.\n"
    "## Requirements\nStrong fundamentals."
)


def make_job(db, recruiter, **kw) -> Job:
    company_id = recruiter.recruiter_profile.company_id
    defaults = dict(
        recruiter_id=recruiter.id,
        company_id=company_id,
        title="Backend Engineer",
        role_category=RoleCategory.backend,
        location="Bengaluru",
        remote_type=RemoteType.hybrid,
        experience_min=1,
        experience_max=3,
        salary_min=1_000_000,
        salary_max=1_800_000,
        skills=["Python", "PostgreSQL"],
        description_md=DESC,
    )
    defaults.update(kw)
    job = Job(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def job_payload(**kw):
    body = {
        "title": "Frontend Engineer",
        "role_category": "frontend",
        "location": "Pune",
        "remote_type": "onsite",
        "experience_min": 2,
        "experience_max": 5,
        "salary_min": 1200000,
        "salary_max": 2000000,
        "skills": ["React", "TypeScript", "react"],
        "description_md": DESC,
    }
    body.update(kw)
    return body


def titles(res):
    return [j["title"] for j in res.json()["items"]]


# ---------- recruiter CRUD ----------


def test_recruiter_creates_job_with_cleaned_skills(client, db):
    _, h = auth_headers(db, client, "rec@example.com", "recruiter", company="Kestrel Systems")
    res = client.post("/api/recruiter/jobs", json=job_payload(), headers=h)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["company"]["name"] == "Kestrel Systems"
    assert data["skills"] == ["React", "TypeScript"]
    assert data["status"] == "open"


def test_remote_jobs_get_remote_location(client, db):
    _, h = auth_headers(db, client, "rec@example.com", "recruiter")
    res = client.post(
        "/api/recruiter/jobs", json=job_payload(remote_type="remote", location="Pune"), headers=h
    )
    assert res.json()["location"] == "Remote"


def test_job_validation_errors(client, db):
    _, h = auth_headers(db, client, "rec@example.com", "recruiter")
    bad = job_payload(experience_min=6, experience_max=2)
    assert client.post("/api/recruiter/jobs", json=bad, headers=h).status_code == 422
    bad = job_payload(salary_min=3000000, salary_max=1000000)
    assert client.post("/api/recruiter/jobs", json=bad, headers=h).status_code == 422
    assert (
        client.post("/api/recruiter/jobs", json=job_payload(skills=[]), headers=h).status_code
        == 422
    )


def test_seeker_cannot_create_job(client, db):
    _, h = auth_headers(db, client, "s@example.com", "seeker")
    assert client.post("/api/recruiter/jobs", json=job_payload(), headers=h).status_code == 403


def test_recruiter_edits_and_closes_own_job_only(client, db):
    owner, h_owner = auth_headers(db, client, "owner@example.com", "recruiter")
    _, h_other = auth_headers(db, client, "other@example.com", "recruiter", company="Other Co")
    job = make_job(db, owner)

    res = client.patch(f"/api/recruiter/jobs/{job.id}", json={"title": "X"}, headers=h_owner)
    assert res.status_code == 422  # title too short
    res = client.patch(
        f"/api/recruiter/jobs/{job.id}", json={"title": "Senior Backend Engineer"}, headers=h_owner
    )
    assert res.status_code == 200
    assert res.json()["title"] == "Senior Backend Engineer"

    assert (
        client.patch(
            f"/api/recruiter/jobs/{job.id}", json={"title": "Hacked"}, headers=h_other
        ).status_code
        == 403
    )
    assert client.post(f"/api/recruiter/jobs/{job.id}/close", headers=h_other).status_code == 403

    res = client.post(f"/api/recruiter/jobs/{job.id}/close", headers=h_owner)
    assert res.json()["status"] == "closed"
    res = client.post(f"/api/recruiter/jobs/{job.id}/reopen", headers=h_owner)
    assert res.json()["status"] == "open"


def test_patch_rejects_inverted_ranges(client, db):
    owner, h = auth_headers(db, client, "owner@example.com", "recruiter")
    job = make_job(db, owner)
    res = client.patch(f"/api/recruiter/jobs/{job.id}", json={"experience_min": 9}, headers=h)
    assert res.status_code == 422


def test_unknown_job_is_404(client, db):
    _, h = auth_headers(db, client, "owner@example.com", "recruiter")
    assert client.patch("/api/recruiter/jobs/999", json={}, headers=h).status_code == 404
    assert client.get("/api/jobs/999").status_code == 404


def test_recruiter_lists_only_own_jobs(client, db):
    owner, h = auth_headers(db, client, "owner@example.com", "recruiter")
    other = make_user(db, "other@example.com", "recruiter", company="Other Co")
    make_job(db, owner, title="Mine")
    make_job(db, other, title="Theirs")
    res = client.get("/api/recruiter/jobs", headers=h)
    assert [j["title"] for j in res.json()] == ["Mine"]


# ---------- search ----------


def test_full_text_search_over_title_skills_description(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    make_job(db, rec, title="Data Scientist", skills=["Python", "Pandas"], role_category="data_ml")
    make_job(db, rec, title="Android Developer", skills=["Kotlin"], role_category="mobile")
    make_job(
        db,
        rec,
        title="Platform Engineer",
        skills=["Go"],
        description_md=DESC + " You will run Kubernetes clusters.",
    )
    assert titles(client.get("/api/jobs", params={"q": "kotlin"})) == ["Android Developer"]
    assert titles(client.get("/api/jobs", params={"q": "data scientist"})) == ["Data Scientist"]
    assert titles(client.get("/api/jobs", params={"q": "kubernetes"})) == ["Platform Engineer"]
    # partial word falls back to title substring
    assert titles(client.get("/api/jobs", params={"q": "andro"})) == ["Android Developer"]
    assert client.get("/api/jobs", params={"q": "cobol"}).json()["total"] == 0


def test_title_match_outranks_description_match(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    make_job(db, rec, title="QA Engineer", description_md=DESC + " Some Selenium work.")
    make_job(db, rec, title="Selenium Automation Engineer", skills=["Selenium"])
    assert titles(client.get("/api/jobs", params={"q": "selenium"}))[0] == (
        "Selenium Automation Engineer"
    )


def test_filters(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    make_job(db, rec, title="A", location="Hyderabad", experience_min=0, experience_max=2)
    make_job(
        db,
        rec,
        title="B",
        location="Remote",
        remote_type=RemoteType.remote,
        salary_min=3_000_000,
        salary_max=4_000_000,
        experience_min=5,
        experience_max=8,
    )
    make_job(db, rec, title="C", location="Chennai", role_category=RoleCategory.qa)
    make_job(db, rec, title="Closed", status=JobStatus.closed)

    def search(**p):
        return sorted(titles(client.get("/api/jobs", params=p)))

    assert search() == ["A", "B", "C"]
    assert search(location=["Hyderabad", "Remote"]) == ["A", "B"]
    assert search(remote="remote") == ["B"]
    assert search(role="qa") == ["C"]
    assert search(experience=6) == ["B"]
    assert search(experience=1) == ["A", "C"]
    assert search(salary_min=2_500_000) == ["B"]
    assert search(salary_max=2_000_000) == ["A", "C"]


def test_sort_newest_and_salary(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    now = datetime.now(UTC)
    make_job(db, rec, title="Old", posted_at=now - timedelta(days=10), salary_max=5_000_000)
    make_job(db, rec, title="New", posted_at=now, salary_max=2_000_000)
    make_job(db, rec, title="Mid", posted_at=now - timedelta(days=3), salary_max=3_000_000)
    assert titles(client.get("/api/jobs", params={"sort": "newest"})) == ["New", "Mid", "Old"]
    assert titles(client.get("/api/jobs", params={"sort": "salary"})) == ["Old", "Mid", "New"]
    # Without a query or resume, relevance falls back to recency.
    assert titles(client.get("/api/jobs")) == ["New", "Mid", "Old"]


def test_pagination_20_per_page(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    now = datetime.now(UTC)
    for i in range(45):
        make_job(db, rec, title=f"Job {i:02d}", posted_at=now - timedelta(hours=i))
    first = client.get("/api/jobs", params={"sort": "newest"}).json()
    assert first["total"] == 45 and first["pages"] == 3 and len(first["items"]) == 20
    third = client.get("/api/jobs", params={"sort": "newest", "page": 3}).json()
    assert len(third["items"]) == 5
    assert third["items"][-1]["title"] == "Job 44"


def test_invalid_sort_is_422(client):
    assert client.get("/api/jobs", params={"sort": "random"}).status_code == 422


def test_search_cache_invalidated_on_job_create(client, db):
    _, h = auth_headers(db, client, "rec@example.com", "recruiter")
    assert client.get("/api/jobs", params={"q": "typescript"}).json()["total"] == 0
    client.post("/api/recruiter/jobs", json=job_payload(), headers=h)
    assert client.get("/api/jobs", params={"q": "typescript"}).json()["total"] == 1


def test_search_results_are_cached(client, db):
    from app.core.redis import get_redis

    rec = make_user(db, "rec@example.com", "recruiter")
    make_job(db, rec)
    client.get("/api/jobs", params={"q": "python"})
    assert any(k.startswith("search:") for k in get_redis().keys("search:*"))
    # A direct DB insert (bypassing the service) is not visible until the cache expires.
    make_job(db, rec, title="Python Developer")
    assert client.get("/api/jobs", params={"q": "python"}).json()["total"] == 1


def test_autocomplete_titles_and_skills(client, db):
    _, h = auth_headers(db, client, "rec@example.com", "recruiter")
    client.post(
        "/api/recruiter/jobs",
        json=job_payload(title="React Native Developer", skills=["React Native", "Redux"]),
        headers=h,
    )
    res = client.get("/api/jobs/autocomplete", params={"q": "re"}).json()
    texts = {(s["text"], s["kind"]) for s in res}
    assert ("React Native Developer", "title") in texts
    assert ("Redux", "skill") in texts
    # Index refreshes after a job change.
    client.post(
        "/api/recruiter/jobs", json=job_payload(title="Rust Engineer", skills=["Rust"]), headers=h
    )
    assert "Rust Engineer" in [s["text"] for s in client.get("/api/jobs/autocomplete?q=ru").json()]


# ---------- saved jobs ----------


def test_save_and_unsave_job(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    job = make_job(db, rec)
    _, h = auth_headers(db, client, "s@example.com", "seeker")
    assert client.post(f"/api/jobs/{job.id}/save", headers=h).status_code == 204
    assert client.post(f"/api/jobs/{job.id}/save", headers=h).status_code == 204  # idempotent
    assert client.get(f"/api/jobs/{job.id}", headers=h).json()["is_saved"] is True
    saved = client.get("/api/jobs/saved", headers=h).json()
    assert [s["id"] for s in saved] == [job.id]
    assert client.delete(f"/api/jobs/{job.id}/save", headers=h).status_code == 204
    assert client.delete(f"/api/jobs/{job.id}/save", headers=h).status_code == 404
    assert client.get("/api/jobs/saved", headers=h).json() == []


def test_recruiter_cannot_save_jobs(client, db):
    rec, h = auth_headers(db, client, "rec@example.com", "recruiter")
    job = make_job(db, rec)
    assert client.post(f"/api/jobs/{job.id}/save", headers=h).status_code == 403
    assert client.post(f"/api/jobs/{job.id}/save").status_code == 401


def test_job_detail_public(client, db):
    rec = make_user(db, "rec@example.com", "recruiter")
    job = make_job(db, rec)
    res = client.get(f"/api/jobs/{job.id}")
    assert res.status_code == 200
    assert res.json()["description_md"].startswith("## About the role")
