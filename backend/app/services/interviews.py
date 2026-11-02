"""Interview scheduling for applications in the Interview stage."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Interview, Job, User
from app.models.enums import ApplicationStatus, UserRole
from app.services import audit
from app.services.calendar import MODE_LABELS
from app.services.notifications import notify

IST = ZoneInfo("Asia/Kolkata")
MIN_LEAD = timedelta(minutes=5)


def format_when(dt: datetime) -> str:
    return dt.astimezone(IST).strftime("%a %d %b %Y, %I:%M %p IST")


def _check_recruiter(actor: User, app: Application) -> None:
    if actor.role != UserRole.admin and app.job.recruiter_id != actor.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only schedule interviews for your own jobs"
        )


def _check_time(starts_at: datetime) -> datetime:
    if starts_at.tzinfo is None:
        raise HTTPException(422, "Include a time zone offset in starts_at")
    if starts_at < datetime.now(UTC) + MIN_LEAD:
        raise HTTPException(422, "Interview time must be in the future")
    return starts_at


def _notify(db: Session, iv: Interview, kind: str, title_prefix: str) -> None:
    app = iv.application
    where = f" ({iv.location})" if iv.location else ""
    notify(
        db,
        app.seeker,
        kind,
        f"{title_prefix}: {app.job.title} at {app.job.company.name}",
        body=(
            f"{MODE_LABELS[iv.mode]}{where}, {format_when(iv.starts_at)}, "
            f"{iv.duration_minutes} minutes."
            + (f"\n{iv.notes}" if iv.notes and iv.status == "scheduled" else "")
        ),
        link="/applications",
        payload={"interview_id": iv.id, "application_id": app.id},
    )


def schedule(
    db: Session, actor: User, application_id: int, data: dict, request: Request | None = None
) -> Interview:
    app = db.get(Application, application_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    _check_recruiter(actor, app)
    if app.status != ApplicationStatus.interview:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Move the candidate to the Interview stage first"
        )
    iv = Interview(
        application_id=app.id,
        scheduled_by=actor.id,
        starts_at=_check_time(data["starts_at"]),
        duration_minutes=data["duration_minutes"],
        mode=data["mode"],
        location=data.get("location"),
        notes=data.get("notes"),
    )
    db.add(iv)
    db.flush()
    db.refresh(iv)
    _notify(db, iv, "interview_scheduled", "Interview scheduled")
    audit.record(
        db, actor, "interview.schedule", "interview", iv.id, {"application_id": app.id}, request
    )
    db.commit()
    return iv


def get_for_recruiter(db: Session, actor: User, interview_id: int) -> Interview:
    iv = db.get(Interview, interview_id)
    if iv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    _check_recruiter(actor, iv.application)
    return iv


def reschedule(
    db: Session, actor: User, iv: Interview, changes: dict, request: Request | None = None
) -> Interview:
    if iv.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview was cancelled")
    if "starts_at" in changes:
        changes["starts_at"] = _check_time(changes["starts_at"])
    for k, v in changes.items():
        setattr(iv, k, v)
    iv.sequence += 1
    _notify(db, iv, "interview_rescheduled", "Interview updated")
    audit.record(
        db, actor, "interview.reschedule", "interview", iv.id, {"fields": sorted(changes)}, request
    )
    db.commit()
    db.refresh(iv)
    return iv


def cancel(db: Session, actor: User, iv: Interview, request: Request | None = None) -> Interview:
    if iv.status == "cancelled":
        return iv
    iv.status = "cancelled"
    iv.sequence += 1
    _notify(db, iv, "interview_cancelled", "Interview cancelled")
    audit.record(db, actor, "interview.cancel", "interview", iv.id, None, request)
    db.commit()
    db.refresh(iv)
    return iv


def visible_to(db: Session, user: User, upcoming_only: bool = False) -> list[Interview]:
    stmt = select(Interview).join(Application, Application.id == Interview.application_id)
    if user.role == UserRole.seeker:
        stmt = stmt.where(Application.seeker_id == user.id)
    elif user.role == UserRole.recruiter:
        stmt = stmt.join(Job, Job.id == Application.job_id).where(Job.recruiter_id == user.id)
    if upcoming_only:
        stmt = stmt.where(
            Interview.starts_at >= datetime.now(UTC) - timedelta(hours=2),
            Interview.status == "scheduled",
        )
    return list(db.scalars(stmt.order_by(Interview.starts_at).limit(200)).unique())


def get_visible(db: Session, user: User, interview_id: int) -> Interview:
    iv = db.get(Interview, interview_id)
    allowed = iv is not None and (
        user.role == UserRole.admin
        or iv.application.seeker_id == user.id
        or (user.role == UserRole.recruiter and iv.application.job.recruiter_id == user.id)
    )
    if not allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return iv
