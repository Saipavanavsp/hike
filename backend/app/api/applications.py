from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models import Application, Notification, SeekerProfile, User
from app.schemas.applications import (
    ApplyIn,
    CandidateInfo,
    CandidateMatch,
    CandidateResume,
    HistoryItem,
    NotificationList,
    NotificationOut,
    RecruiterApplication,
    SeekerApplication,
)
from app.schemas.jobs import JobListItem
from app.services import applications as app_service
from app.services.matching import match_one

router = APIRouter(prefix="/api", tags=["applications"])
seeker_only = require_role("seeker")


# ---------- serializers (shared with the recruiter router) ----------


def history_items(app: Application) -> list[HistoryItem]:
    return [
        HistoryItem(
            from_status=h.from_status,
            to_status=h.to_status,
            changed_at=h.changed_at,
            changed_by_name=h.actor.full_name if h.actor else None,
            changed_by_role=h.actor.role.value if h.actor else None,
        )
        for h in app.history
    ]


def seeker_view(app: Application) -> SeekerApplication:
    return SeekerApplication(
        id=app.id,
        status=app.status,
        note=app.note,
        applied_at=app.applied_at,
        updated_at=app.updated_at,
        job=JobListItem.model_validate(app.job),
        history=history_items(app),
    )


def recruiter_view(db: Session, app: Application, with_match: bool = True) -> RecruiterApplication:
    profile = db.get(SeekerProfile, app.seeker_id)
    # resume is None when the candidate deleted it: the application stays, its data does not.
    resume = app.resume
    breakdown = match_one(db, resume, app.job_id) if with_match and resume else None
    years = resume.years_experience if resume is not None else None
    return RecruiterApplication(
        id=app.id,
        job_id=app.job_id,
        status=app.status,
        note=app.note,
        applied_at=app.applied_at,
        updated_at=app.updated_at,
        candidate=CandidateInfo(
            id=app.seeker.id,
            name=app.seeker.full_name,
            email=app.seeker.email,
            phone=profile.phone if profile else None,
            location=profile.current_location if profile else None,
            years_experience=float(years) if years is not None else None,
        ),
        resume=(
            CandidateResume(
                id=resume.id,
                filename=resume.original_filename,
                skills=list(resume.skills or []),
                predicted_category=(
                    resume.predicted_category.value if resume.predicted_category else None
                ),
            )
            if resume is not None
            else None
        ),
        match=CandidateMatch(**breakdown) if breakdown else None,
    )


# ---------- seeker endpoints ----------


@router.post("/applications", response_model=SeekerApplication, status_code=201)
def apply(data: ApplyIn, db: Session = Depends(get_db), user: User = Depends(seeker_only)):
    return seeker_view(app_service.apply_to_job(db, user, data.job_id, data.note))


@router.get("/applications", response_model=list[SeekerApplication])
def my_applications(db: Session = Depends(get_db), user: User = Depends(seeker_only)):
    apps = db.scalars(
        select(Application)
        .where(Application.seeker_id == user.id)
        .order_by(Application.applied_at.desc())
    ).unique()
    return [seeker_view(a) for a in apps]


@router.get("/applications/{application_id}")
def get_application(
    application_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    app = app_service.get_application_for(db, user, application_id)
    if app.seeker_id == user.id:
        return seeker_view(app)
    return recruiter_view(db, app)


# ---------- notifications ----------


@router.get("/notifications", response_model=NotificationList, tags=["notifications"])
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(30)
    )
    unread = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    return NotificationList(items=[NotificationOut.model_validate(n) for n in items], unread=unread)


@router.post("/notifications/{notification_id}/read", status_code=204, tags=["notifications"])
def mark_read(
    notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    n.read_at = n.read_at or datetime.now(UTC)
    db.commit()
    return Response(status_code=204)


@router.post("/notifications/read-all", status_code=204, tags=["notifications"])
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()
    return Response(status_code=204)
