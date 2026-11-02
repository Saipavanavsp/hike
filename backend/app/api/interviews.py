from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models import Interview, User
from app.services import interviews as interview_service
from app.services.calendar import build_ics, google_calendar_url

router = APIRouter(prefix="/api", tags=["interviews"])
recruiter_only = require_role("recruiter", "admin")


class InterviewIn(BaseModel):
    starts_at: datetime
    duration_minutes: int = Field(45, ge=15, le=480)
    mode: str = Field(pattern="^(video|phone|onsite)$")
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)


class InterviewUpdate(BaseModel):
    starts_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    mode: str | None = Field(default=None, pattern="^(video|phone|onsite)$")
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)


class InterviewOut(BaseModel):
    id: int
    application_id: int
    job_id: int
    job_title: str
    company: str
    candidate_name: str
    starts_at: datetime
    duration_minutes: int
    mode: str
    location: str | None
    notes: str | None
    status: str
    google_calendar_url: str


def interview_out(iv: Interview) -> InterviewOut:
    app = iv.application
    return InterviewOut(
        id=iv.id,
        application_id=app.id,
        job_id=app.job_id,
        job_title=app.job.title,
        company=app.job.company.name,
        candidate_name=app.seeker.full_name,
        starts_at=iv.starts_at,
        duration_minutes=iv.duration_minutes,
        mode=iv.mode,
        location=iv.location,
        notes=iv.notes,
        status=iv.status,
        google_calendar_url=google_calendar_url(iv),
    )


def _clean(text: str | None) -> str | None:
    return (text or "").strip() or None


@router.post(
    "/recruiter/applications/{application_id}/interviews",
    response_model=InterviewOut,
    status_code=201,
)
def schedule_interview(
    application_id: int,
    data: InterviewIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    payload = data.model_dump()
    payload["location"], payload["notes"] = _clean(data.location), _clean(data.notes)
    iv = interview_service.schedule(db, user, application_id, payload, request)
    return interview_out(iv)


@router.patch("/recruiter/interviews/{interview_id}", response_model=InterviewOut)
def update_interview(
    interview_id: int,
    data: InterviewUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    iv = interview_service.get_for_recruiter(db, user, interview_id)
    changes = data.model_dump(exclude_unset=True)
    for key in ("location", "notes"):
        if key in changes:
            changes[key] = _clean(changes[key])
    return interview_out(interview_service.reschedule(db, user, iv, changes, request))


@router.post("/recruiter/interviews/{interview_id}/cancel", response_model=InterviewOut)
def cancel_interview(
    interview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    iv = interview_service.get_for_recruiter(db, user, interview_id)
    return interview_out(interview_service.cancel(db, user, iv, request))


@router.get("/interviews", response_model=list[InterviewOut])
def list_interviews(
    upcoming: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Seekers see their own interviews; recruiters those for their jobs; admins all."""
    return [interview_out(iv) for iv in interview_service.visible_to(db, user, upcoming)]


@router.get("/interviews/{interview_id}/ics")
def download_ics(
    interview_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    iv = interview_service.get_visible(db, user, interview_id)
    return Response(
        build_ics(iv),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="interview-{iv.id}.ics"',
            "Cache-Control": "private, no-store",
        },
    )
