from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ApplicationStatus
from app.schemas.jobs import JobListItem


class ApplyIn(BaseModel):
    job_id: int
    note: str | None = Field(default=None, max_length=500)


class StatusChangeIn(BaseModel):
    status: ApplicationStatus


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    changed_at: datetime
    changed_by_name: str | None = None
    changed_by_role: str | None = None


class SeekerApplication(BaseModel):
    id: int
    status: ApplicationStatus
    note: str | None
    applied_at: datetime
    updated_at: datetime
    job: JobListItem
    history: list[HistoryItem]


class CandidateInfo(BaseModel):
    id: int
    name: str
    email: str
    # Visible to the recruiter of the job the seeker applied to; never to other seekers.
    phone: str | None
    location: str | None
    years_experience: float | None


class CandidateResume(BaseModel):
    id: int
    filename: str
    skills: list[str]
    predicted_category: str | None


class CandidateMatch(BaseModel):
    score: int
    skills_matched: list[str]
    skills_missing: list[str]
    skills_ratio: str
    experience_ok: bool
    location_ok: bool


class RecruiterApplication(BaseModel):
    id: int
    job_id: int
    status: ApplicationStatus
    note: str | None
    applied_at: datetime
    updated_at: datetime
    candidate: CandidateInfo
    resume: CandidateResume | None  # None if the candidate deleted the resume
    match: CandidateMatch | None


class DayCount(BaseModel):
    date: str
    count: int


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    body: str | None
    link: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread: int
