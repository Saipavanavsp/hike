from app.models import EvalRun
from tests.factories import make_user
from tests.test_jobs_api import make_job


def test_public_stats_are_live(client, db):
    empty = client.get("/api/stats/public").json()
    assert empty["open_jobs"] == 0 and empty["precision_at_5"] is None

    rec = make_user(db, "rec@example.com", "recruiter")
    make_user(db, "s1@example.com")
    make_user(db, "s2@example.com")
    make_user(db, "gone@example.com", is_active=False)
    make_job(db, rec)
    make_job(db, rec, status="closed")
    db.add(
        EvalRun(
            metrics={
                "matching": {
                    "methods": {"hike": {"precision_at_5": 0.71}, "tfidf": {"precision_at_5": 0.6}}
                }
            }
        )
    )
    db.commit()

    s = client.get("/api/stats/public").json()
    assert s["open_jobs"] == 1
    assert s["companies"] == 1
    assert s["recruiters"] == 1
    assert s["candidates"] == 2
    assert s["precision_at_5"] == 0.71
    assert s["tfidf_precision_at_5"] == 0.6
    assert s["eval_run_at"]
