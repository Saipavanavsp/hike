import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Job, User
from app.models.enums import JobStatus, RemoteType, UserRole
from app.schemas.jobs import JobCreate, JobUpdate
from app.services.cache import bump_jobs_version
from app.services.companies import get_or_create_company

log = logging.getLogger(__name__)


def get_job_or_404(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


def get_owned_job(db: Session, job_id: int, user: User) -> Job:
    """The job if `user` may manage it (its recruiter, or an admin), else 403/404."""
    job = get_job_or_404(db, job_id)
    if user.role != UserRole.admin and job.recruiter_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only manage your own jobs")
    return job


def _normalise_location(job: Job) -> None:
    if job.remote_type == RemoteType.remote:
        job.location = "Remote"


def create_job(db: Session, recruiter: User, data: JobCreate) -> Job:
    if data.company_name:
        company = get_or_create_company(db, data.company_name)
    elif recruiter.recruiter_profile and recruiter.recruiter_profile.company_id:
        company = recruiter.recruiter_profile.company
    else:
        raise HTTPException(422, "Company name is required")
    job = Job(
        recruiter_id=recruiter.id,
        company_id=company.id,
        **data.model_dump(exclude={"company_name"}),
    )
    _normalise_location(job)
    db.add(job)
    db.commit()
    db.refresh(job)
    on_job_changed(db, job, new_listing=True)
    return job


def update_job(db: Session, job: Job, data: JobUpdate) -> Job:
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(job, k, v)
    if job.experience_min > job.experience_max:
        db.rollback()
        raise HTTPException(
            422,
            "Minimum experience cannot exceed maximum experience",
        )
    if job.salary_min > job.salary_max:
        db.rollback()
        raise HTTPException(422, "Minimum salary cannot exceed maximum salary")
    _normalise_location(job)
    db.commit()
    db.refresh(job)
    on_job_changed(db, job)
    return job


def set_job_status(db: Session, job: Job, new_status: JobStatus) -> Job:
    job.status = new_status
    job.closed_at = datetime.now(UTC) if new_status == JobStatus.closed else None
    db.commit()
    db.refresh(job)
    on_job_changed(db, job, new_listing=new_status == JobStatus.open)
    return job


def on_job_changed(db: Session, job: Job, new_listing: bool = False) -> None:
    """Invalidate search cache + autocomplete index (both keyed on the jobs version), then
    re-embed the job and re-score its applicants in the background. If those tasks fail,
    matching still recomputes missing embeddings and stale scores lazily."""
    from app.tasks.definitions import embed_job, score_job_candidates
    from app.tasks.tracking import enqueue

    bump_jobs_version()
    enqueue(embed_job, job.id, ref_id=job.id)
    has_applicants = db.scalar(select(Application.id).where(Application.job_id == job.id).limit(1))
    if has_applicants is not None:
        enqueue(score_job_candidates, job.id, ref_id=job.id)
    if new_listing:
        from app.tasks.definitions import saved_search_alerts

        enqueue(saved_search_alerts, job.id, ref_id=job.id)
