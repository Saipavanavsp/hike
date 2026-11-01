from pathlib import Path

from app.models import SeekerProfile
from app.services.resume_parser import DOCX_MIME, PDF_MIME
from tests.factories import auth_headers, fetch_resume_file, post_resume

FIXTURES = Path(__file__).parent / "fixtures"


def upload(client, headers, name="priya_sharma_backend.pdf", mime=PDF_MIME, data=None, **kw):
    data = data if data is not None else (FIXTURES / name).read_bytes()
    return post_resume(client, headers, name, data, mime, **kw)


def test_upload_parses_and_returns_draft(client, db):
    _, h = auth_headers(db, client, "priya@example.com")
    res = upload(client, h)
    assert res.status_code == 202, res.text
    body = res.json()
    # Tasks run inline in tests, so parsing has already finished.
    assert body["status"] == "ready"
    assert body["consent_at"] is not None
    assert body["is_current"] is False
    assert body["parsed"]["email"] == "priya.sharma.dev@example.com"
    assert body["parsed"]["phone"] == "+919876543210"  # visible to the owner
    assert "FastAPI" in body["skills"]


def test_upload_docx(client, db):
    _, h = auth_headers(db, client, "arjun@example.com")
    res = upload(client, h, "arjun_menon_frontend.docx", DOCX_MIME)
    assert res.status_code == 202
    assert res.json()["years_experience"] == 4.0


def test_upload_requires_consent(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    res = upload(client, h, consent=False)
    assert res.status_code == 422
    assert "agree" in res.json()["detail"]
    assert client.get("/api/resumes", headers=h).json() == []


def test_upload_rejects_wrong_type_and_size(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    assert upload(client, h, "cv.txt", "text/plain", b"hello world").status_code == 422
    assert upload(client, h, "cv.pdf", PDF_MIME, b"not really a pdf").status_code == 422
    big = b"%PDF-1.4" + b"0" * (5 * 1024 * 1024)
    res = upload(client, h, "big.pdf", PDF_MIME, big)
    assert res.status_code == 413
    assert "5 MB" in res.json()["detail"]


def test_unreadable_pdf_is_accepted_then_marked_failed(client, db):
    """Extraction happens in the background, so its failure is reported on the resume."""
    _, h = auth_headers(db, client, "s@example.com")
    res = upload(client, h, "cv.pdf", PDF_MIME, b"%PDF-1.4 garbage that is not a real pdf")
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "failed"
    assert "Could not read text" in body["parse_error"]
    # A failed resume cannot be confirmed.
    res = client.put(f"/api/resumes/{body['id']}", json={"skills": []}, headers=h)
    assert res.status_code == 409


def test_only_seekers_upload(client, db):
    _, h = auth_headers(db, client, "rec@example.com", "recruiter")
    assert upload(client, h).status_code == 403
    assert upload(client, {}).status_code == 401


def test_confirm_makes_current_and_updates_profile(client, db):
    user, h = auth_headers(db, client, "priya@example.com")
    first = upload(client, h).json()
    res = client.put(
        f"/api/resumes/{first['id']}",
        json={"skills": ["python", "Postgres", "Kafka", "Internal Tool"], "years_experience": 5},
        headers=h,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_current"] is True
    assert body["skills"] == ["Python", "PostgreSQL", "Apache Kafka", "Internal Tool"]
    # Embedding + classification ran as a background task.
    assert body["predicted_category"] == "backend"

    profile = db.get(SeekerProfile, user.id)
    db.refresh(profile)
    assert float(profile.years_experience) == 5.0
    assert profile.phone == "+919876543210"
    assert profile.current_location == "Hyderabad"

    # A second confirmed resume replaces the first as current.
    second = upload(client, h, "kavya_iyer_data.pdf").json()
    client.put(f"/api/resumes/{second['id']}", json={"skills": ["Python"]}, headers=h)
    current = client.get("/api/resumes/current", headers=h).json()
    assert current["id"] == second["id"]
    all_resumes = client.get("/api/resumes", headers=h).json()
    assert [r["is_current"] for r in all_resumes] == [True, False]


def test_current_404_when_none(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    assert client.get("/api/resumes/current", headers=h).status_code == 404


def test_seekers_cannot_see_each_others_resumes(client, db):
    _, h1 = auth_headers(db, client, "a@example.com")
    _, h2 = auth_headers(db, client, "b@example.com")
    rid = upload(client, h1).json()["id"]
    assert client.get(f"/api/resumes/{rid}", headers=h2).status_code == 404
    assert client.put(f"/api/resumes/{rid}", json={"skills": []}, headers=h2).status_code == 404
    assert client.delete(f"/api/resumes/{rid}", headers=h2).status_code == 404
    assert client.post(f"/api/resumes/{rid}/link", headers=h2).status_code == 404


def test_owner_and_admin_can_download_file(client, db):
    _, h = auth_headers(db, client, "a@example.com")
    _, admin = auth_headers(db, client, "admin@example.com", "admin")
    rid = upload(client, h).json()["id"]
    res = fetch_resume_file(client, h, rid)
    assert res.status_code == 200
    assert res.headers["content-type"] == PDF_MIME
    assert res.headers["cache-control"] == "private, no-store"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.content.startswith(b"%PDF-")
    assert fetch_resume_file(client, admin, rid).status_code == 200


def test_task_status_visible_to_owner_only(client, db):
    from sqlalchemy import select

    from app.models import BackgroundTask

    _, h = auth_headers(db, client, "a@example.com")
    _, other = auth_headers(db, client, "b@example.com")
    rid = upload(client, h).json()["id"]
    task = db.scalar(
        select(BackgroundTask).where(
            BackgroundTask.ref_type == "resume",
            BackgroundTask.ref_id == rid,
            BackgroundTask.kind == "process_resume",
        )
    )
    res = client.get(f"/api/tasks/{task.id}", headers=h)
    assert res.status_code == 200
    assert res.json()["status"] == "succeeded"
    assert res.json()["attempts"] == 1
    assert client.get(f"/api/tasks/{task.id}", headers=other).status_code == 404


def test_skills_search_endpoint(client):
    res = client.get("/api/skills", params={"q": "post"})
    assert res.status_code == 200
    assert "PostgreSQL" in res.json()
