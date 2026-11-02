from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models import Company, Job, RecruiterProfile, User
from app.models.enums import JobStatus
from app.schemas.jobs import JobListItem
from app.services import audit

router = APIRouter(prefix="/api", tags=["companies"])
recruiter_only = require_role("recruiter", "admin")


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    logo_url: str | None
    website: str | None
    industry: str | None
    size_range: str | None
    hq_city: str | None
    about: str | None


class CompanyPage(BaseModel):
    company: CompanyOut
    open_jobs: list[JobListItem]
    recruiters: int


class CompanyUpdate(BaseModel):
    website: str | None = Field(default=None, max_length=300)
    industry: str | None = Field(default=None, max_length=80)
    size_range: str | None = Field(default=None, max_length=40)
    hq_city: str | None = Field(default=None, max_length=80)
    about: str | None = Field(default=None, max_length=1000)

    @field_validator("website")
    @classmethod
    def _website(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if not v:
            return None
        if not v.startswith(("https://", "http://")):
            raise ValueError("Website must start with https:// or http://")
        return v

    @field_validator("industry", "size_range", "hq_city", "about")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return (v or "").strip() or None


@router.get("/companies/{slug}", response_model=CompanyPage)
def company_page(slug: str, db: Session = Depends(get_db)):
    """Public company profile with its open jobs."""
    company = db.scalar(select(Company).where(Company.slug == slug))
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    jobs = db.scalars(
        select(Job)
        .where(Job.company_id == company.id, Job.status == JobStatus.open)
        .order_by(Job.posted_at.desc())
        .limit(50)
    )
    recruiters = db.scalar(
        select(func.count())
        .select_from(RecruiterProfile)
        .where(RecruiterProfile.company_id == company.id)
    )
    return CompanyPage(
        company=CompanyOut.model_validate(company),
        open_jobs=[JobListItem.model_validate(j) for j in jobs],
        recruiters=recruiters,
    )


def _my_company(user: User) -> Company:
    profile = user.recruiter_profile
    if profile is None or profile.company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Your account is not linked to a company")
    return profile.company


@router.get("/recruiter/company", response_model=CompanyOut)
def get_my_company(user: User = Depends(recruiter_only)):
    return _my_company(user)


@router.put("/recruiter/company", response_model=CompanyOut)
def update_my_company(
    data: CompanyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    company = _my_company(user)
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(company, k, v)
    audit.record(
        db, user, "company.update", "company", company.id, {"fields": sorted(changes)}, request
    )
    db.commit()
    db.refresh(company)
    return company
