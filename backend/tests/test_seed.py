import random

from sqlalchemy import func, select

from app.models import Application, ApplicationStatusHistory, Company, Job, Resume, User
from app.models.enums import ApplicationStatus, UserRole
from seed import seed as seed_module


def count(db, model, *where):
    return db.scalar(select(func.count()).select_from(model).where(*where))


def test_seed_builds_the_demo_dataset(db, client):
    summary = seed_module.seed(db, random.Random(7), run_eval=False)
    assert summary["companies"] == 20 and summary["jobs"] == 50 and summary["seekers"] == 20
    assert count(db, User, User.role == UserRole.admin) == 1
    assert count(db, User, User.role == UserRole.recruiter) == 3
    assert count(db, Company) == 20
    assert count(db, Job) == 50
    assert count(db, Resume, Resume.is_current.is_(True)) == 20
    assert count(db, Resume, Resume.predicted_category.is_not(None)) == 20
    assert count(db, Application) == 60
    # Every pipeline stage is represented, and each application has a consistent history.
    statuses = {s for (s,) in db.execute(select(Application.status).distinct())}
    assert statuses == set(ApplicationStatus)
    for app in db.scalars(select(Application)):
        history = list(
            db.scalars(
                select(ApplicationStatusHistory)
                .where(ApplicationStatusHistory.application_id == app.id)
                .order_by(ApplicationStatusHistory.changed_at)
            )
        )
        assert history[0].from_status is None
        assert history[-1].to_status == app.status
        times = [h.changed_at for h in history]
        assert times == sorted(times) and len(set(times)) == len(times)

    # Demo logins documented in the README work.
    for email, password in [
        ("admin@example.com", "Admin@123"),
        ("meera@example.com", "Recruiter@123"),
        ("rahul@example.com", "Seeker@123"),
    ]:
        res = client.post("/api/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, email

    # A seeded seeker sees match scores and a seeded recruiter sees ranked candidates.
    token = client.post(
        "/api/auth/login", json={"email": "rahul@example.com", "password": "Seeker@123"}
    ).json()["access_token"]
    page = client.get("/api/jobs", headers={"Authorization": f"Bearer {token}"}).json()
    assert page["total"] == 50
    assert all(j["match_score"] is not None for j in page["items"])


def test_seed_if_empty_is_idempotent(db):
    assert seed_module.main(["--if-empty", "--no-eval"]) == 0
    assert count(db, Job) == 50
    assert seed_module.main(["--if-empty", "--no-eval"]) == 0  # second run is a no-op
    assert count(db, Job) == 50
    assert seed_module.main(["--no-eval"]) == 1  # refuses to seed a non-empty database
