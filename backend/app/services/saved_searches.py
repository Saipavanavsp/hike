"""Saved searches and job alerts.

When a job is posted (or reopened), a background task checks it against every saved search
with alerts on, using the same filters and full-text match as the search page, and notifies
each matching seeker (in the app, and by email unless they turned email off).
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, Notification, SavedSearch, User
from app.models.enums import JobStatus
from app.services.notifications import notify
from app.services.search import SearchParams, job_matches

MAX_PER_USER = 20


def to_params(p: dict) -> SearchParams:
    return SearchParams(
        q=p.get("q", ""),
        locations=list(p.get("location", [])),
        roles=list(p.get("role", [])),
        remote=list(p.get("remote", [])),
        experience=p.get("experience"),
    )


def describe(p: dict) -> str:
    parts = [f'"{p["q"]}"'] if p.get("q") else []
    for key in ("location", "role", "remote"):
        if p.get(key):
            parts.append(", ".join(p[key]))
    if p.get("experience") is not None:
        parts.append(f"{p['experience']} yrs")
    return " · ".join(parts) or "All jobs"


def alert_for_job(db: Session, job_id: int) -> dict:
    job = db.get(Job, job_id)
    if job is None or job.status != JobStatus.open:
        return {"skipped": "job not open"}
    notified = 0
    searches = db.scalars(
        select(SavedSearch)
        .join(User, User.id == SavedSearch.user_id)
        .where(SavedSearch.alerts_enabled.is_(True), User.is_active.is_(True))
    )
    for s in searches:
        if not job_matches(db, to_params(s.params), job.id):
            continue
        # Idempotent: a rerun (or a reopen of the same job) never alerts twice.
        already = db.scalar(
            select(Notification.id).where(
                Notification.user_id == s.user_id,
                Notification.type == "saved_search_match",
                Notification.payload.contains({"saved_search_id": s.id, "job_id": job.id}),
            )
        )
        if already is not None:
            continue
        notify(
            db,
            db.get(User, s.user_id),
            "saved_search_match",
            f"New job for “{s.name}”: {job.title} at {job.company.name}",
            body=f"{job.location} · {job.experience_min}-{job.experience_max} yrs",
            link=f"/jobs/{job.id}",
            payload={"saved_search_id": s.id, "job_id": job.id},
        )
        s.last_alert_at = datetime.now(UTC)
        notified += 1
    db.commit()
    return {"notified": notified}
