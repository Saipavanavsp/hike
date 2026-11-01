from app.models import Application
from app.models.enums import JobStatus
from tests.factories import auth_headers, login, make_user
from tests.test_applications import give_resume
from tests.test_jobs_api import make_job


def admin(client, db):
    _, h = auth_headers(db, client, "admin@example.com", "admin", full_name="Site Admin")
    return h


def test_admin_only(client, db):
    _, sh = auth_headers(db, client, "s@example.com")
    _, rh = auth_headers(db, client, "r@example.com", "recruiter")
    for path in ["/api/admin/users", "/api/admin/jobs", "/api/admin/applications"]:
        assert client.get(path, headers=sh).status_code == 403
        assert client.get(path, headers=rh).status_code == 403
        assert client.get(path).status_code == 401


def test_users_search_sort_paginate(client, db):
    h = admin(client, db)
    for i in range(25):
        make_user(db, f"user{i:02d}@example.com", full_name=f"User {i:02d}")
    make_user(
        db, "rec@example.com", "recruiter", company="Kestrel Systems", full_name="Zed Recruiter"
    )

    first = client.get(
        "/api/admin/users", params={"sort": "email", "order": "asc"}, headers=h
    ).json()
    assert first["total"] == 27 and first["pages"] == 2 and len(first["items"]) == 20
    assert first["items"][0]["email"] == "admin@example.com"

    res = client.get("/api/admin/users", params={"q": "zed"}, headers=h).json()
    assert [u["company"] for u in res["items"]] == ["Kestrel Systems"]
    res = client.get("/api/admin/users", params={"role": "recruiter"}, headers=h).json()
    assert res["total"] == 1
    assert (
        client.get("/api/admin/users", params={"sort": "password_hash"}, headers=h).status_code
        == 422
    )


def test_bulk_deactivate_and_activate(client, db):
    h = admin(client, db)
    u1 = make_user(db, "a@example.com")
    u2 = make_user(db, "b@example.com")
    victim = login(client, "a@example.com")

    res = client.post("/api/admin/users/deactivate", json={"ids": [u1.id, u2.id]}, headers=h)
    assert res.json() == {"updated": 2}
    # Deactivated users are locked out at once (access token rejected, refresh revoked).
    assert client.get("/api/auth/me", headers=victim).status_code == 401
    assert client.post("/api/auth/refresh").status_code == 401

    res = client.post("/api/admin/users/activate", json={"ids": [u1.id]}, headers=h)
    assert res.json() == {"updated": 1}
    assert (
        client.post("/api/admin/users/deactivate", json={"ids": []}, headers=h).status_code == 422
    )


def test_admin_cannot_deactivate_self(client, db):
    h = admin(client, db)
    me = client.get("/api/auth/me", headers=h).json()
    res = client.post("/api/admin/users/deactivate", json={"ids": [me["id"]]}, headers=h)
    assert res.status_code == 422


def test_jobs_table_and_bulk_close(client, db):
    h = admin(client, db)
    rec = make_user(db, "rec@example.com", "recruiter", full_name="Meera Nair")
    j1 = make_job(db, rec, title="Alpha Engineer")
    j2 = make_job(db, rec, title="Beta Engineer")
    _, sh = auth_headers(db, client, "s@example.com")
    give_resume(client, sh)
    client.post("/api/applications", json={"job_id": j1.id}, headers=sh)

    res = client.get("/api/admin/jobs", params={"sort": "applications"}, headers=h).json()
    assert [(j["title"], j["applications"]) for j in res["items"]] == [
        ("Alpha Engineer", 1),
        ("Beta Engineer", 0),
    ]
    assert res["items"][0]["recruiter"] == "Meera Nair"

    assert client.get("/api/jobs", params={"q": "beta"}).json()["total"] == 1
    res = client.post("/api/admin/jobs/close", json={"ids": [j1.id, j2.id]}, headers=h)
    assert res.json() == {"updated": 2}
    # Search cache is invalidated: closed jobs disappear from seeker search.
    assert client.get("/api/jobs", params={"q": "beta"}).json()["total"] == 0
    db.expire_all()
    assert db.get(type(j1), j1.id).status == JobStatus.closed
    res = client.get("/api/admin/jobs", params={"status": "closed", "q": "alpha"}, headers=h).json()
    assert res["total"] == 1


def test_applications_table(client, db):
    h = admin(client, db)
    rec = make_user(db, "rec@example.com", "recruiter")
    job = make_job(db, rec, title="Gamma Developer")
    _, sh = auth_headers(db, client, "priya@example.com", full_name="Priya Sharma")
    give_resume(client, sh)
    client.post("/api/applications", json={"job_id": job.id}, headers=sh)

    res = client.get("/api/admin/applications", params={"q": "gamma"}, headers=h).json()
    assert res["total"] == 1
    row = res["items"][0]
    assert row["candidate"] == "Priya Sharma" and row["status"] == "applied"
    assert db.query(Application).count() == 1
    res = client.get("/api/admin/applications", params={"status": "offer"}, headers=h).json()
    assert res["total"] == 0
