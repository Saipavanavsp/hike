from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import JobStatus, RemoteType, RoleCategory
from app.schemas.auth import CompanyBrief

MAX_SALARY = 100_000_000  # 10 crore INR


class ScoreComponent(BaseModel):
    """One part of the match score: points earned out of its weight, and why."""

    key: str
    label: str
    weight: int
    points: float
    detail: str


class MatchBreakdown(BaseModel):
    score: int
    components: list[ScoreComponent] = []
    skills_matched: list[str]
    skills_missing: list[str]
    skills_ratio: str
    experience_ok: bool
    experience_years: float | None
    location_ok: bool
    semantic: float
    cosine: float | None = None
    skill_overlap: float
    experience_fit: float
    location_fit: float


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: CompanyBrief
    role_category: RoleCategory
    location: str
    remote_type: RemoteType
    experience_min: int
    experience_max: int
    salary_min: int
    salary_max: int
    skills: list[str]
    status: JobStatus
    posted_at: datetime
    match_score: int | None = None


class JobDetail(JobListItem):
    description_md: str
    recruiter_id: int
    is_saved: bool = False
    application_status: str | None = None
    application_id: int | None = None
    match: MatchBreakdown | None = None


class JobPage(BaseModel):
    items: list[JobListItem]
    total: int
    page: int
    page_size: int
    pages: int


class SavedJobItem(JobListItem):
    saved_at: datetime


class Suggestion(BaseModel):
    text: str
    kind: str


class JobBase(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    role_category: RoleCategory
    location: str = Field(min_length=2, max_length=80)
    remote_type: RemoteType
    experience_min: int = Field(ge=0, le=40)
    experience_max: int = Field(ge=0, le=40)
    salary_min: int = Field(gt=0, le=MAX_SALARY)
    salary_max: int = Field(gt=0, le=MAX_SALARY)
    skills: list[str] = Field(min_length=1, max_length=20)
    description_md: str = Field(min_length=50, max_length=20000)


def _clean_skills(skills: list[str]) -> list[str]:
    seen, out = set(), []
    for s in skills:
        s = " ".join(s.split())
        if s and s.lower() not in seen and len(s) <= 60:
            seen.add(s.lower())
            out.append(s)
    return out


class JobCreate(JobBase):
    company_name: str | None = Field(default=None, max_length=120)

    @field_validator("skills")
    @classmethod
    def _skills(cls, v: list[str]) -> list[str]:
        cleaned = _clean_skills(v)
        if not cleaned:
            raise ValueError("Add at least one skill")
        return cleaned

    @model_validator(mode="after")
    def _ranges(self):
        if self.experience_min > self.experience_max:
            raise ValueError("Minimum experience cannot exceed maximum experience")
        if self.salary_min > self.salary_max:
            raise ValueError("Minimum salary cannot exceed maximum salary")
        return self


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    role_category: RoleCategory | None = None
    location: str | None = Field(default=None, min_length=2, max_length=80)
    remote_type: RemoteType | None = None
    experience_min: int | None = Field(default=None, ge=0, le=40)
    experience_max: int | None = Field(default=None, ge=0, le=40)
    salary_min: int | None = Field(default=None, gt=0, le=MAX_SALARY)
    salary_max: int | None = Field(default=None, gt=0, le=MAX_SALARY)
    skills: list[str] | None = Field(default=None, min_length=1, max_length=20)
    description_md: str | None = Field(default=None, min_length=50, max_length=20000)

    @field_validator("skills")
    @classmethod
    def _skills(cls, v: list[str] | None) -> list[str] | None:
        return _clean_skills(v) if v is not None else None


class RecruiterJobItem(JobListItem):
    applications_count: int = 0
    new_count: int = 0
