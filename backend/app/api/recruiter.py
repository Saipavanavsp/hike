from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models import Job, User
from app.models.enums import JobStatus
from app.schemas.jobs import JobCreate, JobDetail, JobUpdate, RecruiterJobItem
from app.services import jobs as job_service

router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])

recruiter_only = require_role("recruiter", "admin")


def application_counts(db: Session, job_ids: list[int]) -> dict[int, tuple[int, int]]:
    """job_id -> (total applications, applications still in 'applied')."""
    return {}


@router.get("/jobs", response_model=list[RecruiterJobItem])
def my_jobs(db: Session = Depends(get_db), user: User = Depends(recruiter_only)):
    jobs = list(
        db.scalars(select(Job).where(Job.recruiter_id == user.id).order_by(Job.posted_at.desc()))
    )
    counts = application_counts(db, [j.id for j in jobs])
    out = []
    for job in jobs:
        item = RecruiterJobItem.model_validate(job)
        item.applications_count, item.new_count = counts.get(job.id, (0, 0))
        out.append(item)
    return out


@router.post("/jobs", response_model=JobDetail, status_code=status.HTTP_201_CREATED)
def create_job(
    data: JobCreate, db: Session = Depends(get_db), user: User = Depends(recruiter_only)
):
    return job_service.create_job(db, user, data)


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_my_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(recruiter_only)):
    return job_service.get_owned_job(db, job_id, user)


@router.patch("/jobs/{job_id}", response_model=JobDetail)
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    job = job_service.get_owned_job(db, job_id, user)
    return job_service.update_job(db, job, data)


@router.post("/jobs/{job_id}/close", response_model=JobDetail)
def close_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(recruiter_only)):
    job = job_service.get_owned_job(db, job_id, user)
    return job_service.set_job_status(db, job, JobStatus.closed)


@router.post("/jobs/{job_id}/reopen", response_model=JobDetail)
def reopen_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(recruiter_only)):
    job = job_service.get_owned_job(db, job_id, user)
    return job_service.set_job_status(db, job, JobStatus.open)
