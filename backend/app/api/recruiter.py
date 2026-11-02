from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.applications import recruiter_view
from app.core.deps import require_role
from app.db.session import get_db
from app.models import Application, Job, User
from app.models.enums import ApplicationStatus, JobStatus, RoleCategory
from app.schemas.applications import DayCount, RecruiterApplication, StatusChangeIn
from app.schemas.jobs import JobCreate, JobDetail, JobUpdate, RecruiterJobItem
from app.services import analytics as analytics_service
from app.services import applications as app_service
from app.services import audit
from app.services import jobs as job_service

router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])

recruiter_only = require_role("recruiter", "admin")


@router.get("/jobs", response_model=list[RecruiterJobItem])
def my_jobs(db: Session = Depends(get_db), user: User = Depends(recruiter_only)):
    jobs = list(
        db.scalars(select(Job).where(Job.recruiter_id == user.id).order_by(Job.posted_at.desc()))
    )
    counts = app_service.counts_by_job(db, [j.id for j in jobs])
    out = []
    for job in jobs:
        item = RecruiterJobItem.model_validate(job)
        item.applications_count, item.new_count = counts.get(job.id, (0, 0))
        out.append(item)
    return out


@router.post("/jobs", response_model=JobDetail, status_code=status.HTTP_201_CREATED)
def create_job(
    data: JobCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    job = job_service.create_job(db, user, data)
    audit.record(db, user, "job.create", "job", job.id, {"title": job.title}, request)
    db.commit()
    return job


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_my_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(recruiter_only)):
    return job_service.get_owned_job(db, job_id, user)


@router.patch("/jobs/{job_id}", response_model=JobDetail)
def update_job(
    job_id: int,
    data: JobUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    job = job_service.get_owned_job(db, job_id, user)
    fields = sorted(data.model_dump(exclude_unset=True))
    job = job_service.update_job(db, job, data)
    audit.record(db, user, "job.update", "job", job.id, {"fields": fields}, request)
    db.commit()
    return job


@router.post("/jobs/{job_id}/close", response_model=JobDetail)
def close_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    job = job_service.get_owned_job(db, job_id, user)
    job = job_service.set_job_status(db, job, JobStatus.closed)
    audit.record(db, user, "job.close", "job", job.id, None, request)
    db.commit()
    return job


@router.post("/jobs/{job_id}/reopen", response_model=JobDetail)
def reopen_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    job = job_service.get_owned_job(db, job_id, user)
    job = job_service.set_job_status(db, job, JobStatus.open)
    audit.record(db, user, "job.reopen", "job", job.id, None, request)
    db.commit()
    return job


@router.get("/jobs/{job_id}/applications", response_model=list[RecruiterApplication])
def job_applications(
    job_id: int,
    status_filter: list[ApplicationStatus] = Query(default=[], alias="status"),
    category: list[RoleCategory] = Query(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    """All candidates for a job, ranked by match score (best first)."""
    job = job_service.get_owned_job(db, job_id, user)
    stmt = select(Application).where(Application.job_id == job.id)
    if status_filter:
        stmt = stmt.where(Application.status.in_(status_filter))
    apps = list(db.scalars(stmt).unique())
    views = [recruiter_view(db, a) for a in apps]
    if category:
        wanted = {c.value for c in category}
        views = [v for v in views if v.resume and v.resume.predicted_category in wanted]
    views.sort(key=lambda v: (-(v.match.score if v.match else -1), v.applied_at))
    return views


@router.patch("/applications/{application_id}/status", response_model=RecruiterApplication)
def move_application(
    application_id: int,
    data: StatusChangeIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    before = app_service.current_status(db, application_id)
    app = app_service.change_status(db, user, application_id, data.status)
    if before is not None and before != app.status:
        audit.record(
            db,
            user,
            "application.status_change",
            "application",
            app.id,
            {"from": before.value, "to": app.status.value, "job_id": app.job_id},
            request,
        )
        db.commit()
    return recruiter_view(db, app)


@router.get("/analytics")
def analytics(
    job_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    """Hiring funnel, conversion, time to first response and time to offer."""
    if job_id is not None:
        job_service.get_owned_job(db, job_id, user)
    return analytics_service.recruiter_analytics(db, user, job_id)


@router.get("/stats/applications-weekly", response_model=list[DayCount])
def applications_weekly(
    job_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(recruiter_only),
):
    if job_id is not None:
        job_service.get_owned_job(db, job_id, user)
    return app_service.weekly_counts(db, user, job_id)
