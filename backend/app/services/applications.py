"""Application pipeline: Applied -> Shortlisted -> Interview -> Offer, with Rejected as an exit."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Application, ApplicationStatusHistory, Job, User
from app.models.enums import ApplicationStatus, JobStatus, UserRole
from app.services.notifications import notify
from app.services.resumes import current_resume

S = ApplicationStatus

# Allowed moves. Forward one stage, reject from any active stage, and step back one stage
# so a recruiter can undo a mistaken drag. Rejected candidates can be reconsidered.
TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    S.applied: {S.shortlisted, S.rejected},
    S.shortlisted: {S.interview, S.rejected, S.applied},
    S.interview: {S.offer, S.rejected, S.shortlisted},
    S.offer: {S.interview},
    S.rejected: {S.applied, S.shortlisted, S.interview},
}

LABELS = {
    S.applied: "Applied",
    S.shortlisted: "Shortlisted",
    S.interview: "Interview",
    S.offer: "Offer",
    S.rejected: "Rejected",
}


def apply_to_job(db: Session, seeker: User, job_id: int, note: str | None) -> Application:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if job.status != JobStatus.open:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This job is no longer accepting applications"
        )
    resume = current_resume(db, seeker.id)
    if resume is None:
        raise HTTPException(422, "Upload and confirm your resume before applying")
    app = Application(
        job_id=job.id, seeker_id=seeker.id, resume_id=resume.id, note=(note or "").strip() or None
    )
    db.add(app)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already applied to this job") from e
    db.add(
        ApplicationStatusHistory(
            application_id=app.id, from_status=None, to_status=S.applied, changed_by=seeker.id
        )
    )
    recruiter = db.get(User, job.recruiter_id)
    if recruiter:
        notify(
            db,
            recruiter,
            "application_received",
            f"New application: {seeker.full_name} for {job.title}",
            body=app.note,
            link=f"/recruiter/jobs/{job.id}",
            payload={"application_id": app.id, "job_id": job.id},
        )
    db.commit()
    db.refresh(app)
    return app


def get_application_for(db: Session, user: User, application_id: int) -> Application:
    """Seeker who applied, the job's recruiter, or an admin. Others get 404."""
    app = db.get(Application, application_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    allowed = (
        user.role == UserRole.admin
        or app.seeker_id == user.id
        or (user.role == UserRole.recruiter and app.job.recruiter_id == user.id)
    )
    if not allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return app


def change_status(
    db: Session, actor: User, application_id: int, new_status: ApplicationStatus
) -> Application:
    app = db.get(Application, application_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if actor.role != UserRole.admin and app.job.recruiter_id != actor.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only manage applications for your own jobs"
        )
    if new_status == app.status:
        return app
    if new_status not in TRANSITIONS[app.status]:
        raise HTTPException(422, f"Cannot move from {LABELS[app.status]} to {LABELS[new_status]}")
    old = app.status
    app.status = new_status
    db.add(
        ApplicationStatusHistory(
            application_id=app.id, from_status=old, to_status=new_status, changed_by=actor.id
        )
    )
    notify(
        db,
        app.seeker,
        "status_changed",
        f"{app.job.title} at {app.job.company.name}: {LABELS[new_status]}",
        body=f"Your application moved from {LABELS[old]} to {LABELS[new_status]}.",
        link="/applications",
        payload={"application_id": app.id, "from": old.value, "to": new_status.value},
    )
    db.commit()
    db.refresh(app)
    return app


def counts_by_job(db: Session, job_ids: list[int]) -> dict[int, tuple[int, int]]:
    """job_id -> (total applications, still in Applied)."""
    if not job_ids:
        return {}
    rows = db.execute(
        select(
            Application.job_id,
            func.count(),
            func.count().filter(Application.status == S.applied),
        )
        .where(Application.job_id.in_(job_ids))
        .group_by(Application.job_id)
    ).all()
    return {job_id: (total, new) for job_id, total, new in rows}


def weekly_counts(db: Session, recruiter: User, job_id: int | None, days: int = 7) -> list[dict]:
    """Applications per day for the last `days` days (oldest first), zero-filled."""
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    day = func.date(func.timezone("UTC", Application.applied_at))
    stmt = (
        select(day.label("day"), func.count())
        .join(Job, Job.id == Application.job_id)
        .where(Application.applied_at >= datetime.combine(start, datetime.min.time(), UTC))
        .group_by("day")
    )
    if recruiter.role != UserRole.admin:
        stmt = stmt.where(Job.recruiter_id == recruiter.id)
    if job_id is not None:
        stmt = stmt.where(Application.job_id == job_id)
    by_day = {d: n for d, n in db.execute(stmt).all()}
    return [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "count": by_day.get(start + timedelta(days=i), 0),
        }
        for i in range(days)
    ]
