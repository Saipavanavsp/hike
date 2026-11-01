"""Admin data tables: users, jobs, applications with search, sorting, pagination, bulk actions."""

import math
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.core.config import settings
from app.core.deps import require_role
from app.core.health import check_db, check_redis, queue_depth, task_counts, worker_status
from app.db.session import get_db
from app.models import (
    Application,
    BackgroundTask,
    Company,
    Job,
    RecruiterProfile,
    RefreshToken,
    User,
)
from app.models.enums import ApplicationStatus, JobStatus, UserRole
from app.services.cache import bump_jobs_version
from app.services.file_scan import clamav_ping

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_only = require_role("admin")
PAGE_SIZE = 20


class BulkIds(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


class BulkResult(BaseModel):
    updated: int


class AdminUser(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    company: str | None


class AdminJob(BaseModel):
    id: int
    title: str
    company: str
    recruiter: str
    location: str
    status: str
    posted_at: datetime
    applications: int


class AdminApplication(BaseModel):
    id: int
    candidate: str
    candidate_email: str
    job_title: str
    company: str
    status: str
    applied_at: datetime


def _page(db: Session, stmt, page: int, row_to_item) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.execute(stmt.limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE)).all()
    return {
        "items": [row_to_item(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "pages": max(1, math.ceil(total / PAGE_SIZE)),
    }


def _order(column, order: str, tiebreak):
    """ORDER BY column (nulls last), then the id in the same direction for a stable order."""
    if order == "asc":
        return column.asc().nulls_last(), tiebreak.asc()
    return column.desc().nulls_last(), tiebreak.desc()


def _like(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# ---------- users ----------


@router.get("/users")
def list_users(
    q: str = Query("", max_length=100),
    role: UserRole | None = None,
    sort: str = Query(
        "created_at", pattern="^(full_name|email|role|created_at|last_login_at|is_active)$"
    ),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    stmt = (
        select(User, Company.name)
        .outerjoin(RecruiterProfile, RecruiterProfile.user_id == User.id)
        .outerjoin(Company, Company.id == RecruiterProfile.company_id)
    )
    if q.strip():
        pattern = _like(q.strip())
        stmt = stmt.where(
            or_(User.full_name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\"))
        )
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(*_order(getattr(User, sort), order, User.id))
    return _page(
        db,
        stmt,
        page,
        lambda r: AdminUser(
            id=r[0].id,
            email=r[0].email,
            full_name=r[0].full_name,
            role=r[0].role.value,
            is_active=r[0].is_active,
            created_at=r[0].created_at,
            last_login_at=r[0].last_login_at,
            company=r[1],
        ),
    )


def _set_active(db: Session, admin: User, ids: list[int], active: bool) -> int:
    if not active and admin.id in ids:
        raise HTTPException(422, "You cannot deactivate your own account")
    res = db.execute(
        update(User)
        .where(User.id.in_(ids), User.is_active.is_(not active))
        .values(is_active=active)
    )
    if not active:
        # Deactivated users lose their sessions immediately.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id.in_(ids), RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
    db.commit()
    return res.rowcount


@router.post("/users/deactivate", response_model=BulkResult)
def deactivate_users(
    data: BulkIds, db: Session = Depends(get_db), admin: User = Depends(admin_only)
):
    return BulkResult(updated=_set_active(db, admin, data.ids, False))


@router.post("/users/activate", response_model=BulkResult)
def activate_users(data: BulkIds, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return BulkResult(updated=_set_active(db, admin, data.ids, True))


# ---------- jobs ----------


@router.get("/jobs")
def list_jobs(
    q: str = Query("", max_length=100),
    status: JobStatus | None = None,
    sort: str = Query(
        "posted_at", pattern="^(title|company|recruiter|location|status|posted_at|applications)$"
    ),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    recruiter = aliased(User)
    app_count = (
        select(Application.job_id, func.count().label("n")).group_by(Application.job_id).subquery()
    )
    n_apps = func.coalesce(app_count.c.n, 0)
    stmt = (
        select(
            Job.id,
            Job.title,
            Company.name,
            recruiter.full_name,
            Job.location,
            Job.status,
            Job.posted_at,
            n_apps,
        )
        .join(Company, Company.id == Job.company_id)
        .join(recruiter, recruiter.id == Job.recruiter_id)
        .outerjoin(app_count, app_count.c.job_id == Job.id)
    )
    if q.strip():
        pattern = _like(q.strip())
        stmt = stmt.where(
            or_(Job.title.ilike(pattern, escape="\\"), Company.name.ilike(pattern, escape="\\"))
        )
    if status:
        stmt = stmt.where(Job.status == status)
    columns = {
        "title": Job.title,
        "company": Company.name,
        "recruiter": recruiter.full_name,
        "location": Job.location,
        "status": Job.status,
        "posted_at": Job.posted_at,
        "applications": n_apps,
    }
    stmt = stmt.order_by(*_order(columns[sort], order, Job.id))
    return _page(
        db,
        stmt,
        page,
        lambda r: AdminJob(
            id=r[0],
            title=r[1],
            company=r[2],
            recruiter=r[3],
            location=r[4],
            status=r[5].value,
            posted_at=r[6],
            applications=r[7],
        ),
    )


@router.post("/jobs/close", response_model=BulkResult)
def close_jobs(data: BulkIds, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    res = db.execute(
        update(Job)
        .where(Job.id.in_(data.ids), Job.status == JobStatus.open)
        .values(status=JobStatus.closed, closed_at=datetime.now(UTC))
    )
    db.commit()
    bump_jobs_version()
    return BulkResult(updated=res.rowcount)


# ---------- system: health, background tasks, retention ----------


class AdminTask(BaseModel):
    id: str
    kind: str
    status: str
    attempts: int
    error: str | None
    ref_type: str | None
    ref_id: int | None
    created_at: datetime
    finished_at: datetime | None


@router.get("/system")
def system_overview(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    db_ok, db_ms = check_db()
    redis_ok, redis_ms = check_redis()
    recent_failures = db.scalars(
        select(BackgroundTask)
        .where(BackgroundTask.status == "failed")
        .order_by(BackgroundTask.created_at.desc())
        .limit(20)
    )
    return {
        "dependencies": {
            "postgres": {"ok": db_ok, "latency_ms": db_ms},
            "redis": {"ok": redis_ok, "latency_ms": redis_ms},
            "clamav": (
                {"ok": clamav_ping(settings.clamav_host, settings.clamav_port)}
                if settings.malware_scan == "clamav"
                else None
            ),
        },
        "worker": worker_status(),
        "queue_depth": queue_depth(),
        "tasks_last_24h": task_counts(24),
        "recent_failures": [_task_out(t) for t in recent_failures],
        "security": {
            "malware_scan": settings.malware_scan,
            "parser_isolation": settings.parser_isolation,
            "files_encrypted": True,
            "signed_url_ttl_seconds": settings.signed_url_ttl_seconds,
        },
        "retention": {
            "unconfirmed_days": settings.retention_unconfirmed_days,
            "old_resume_days": settings.retention_old_resume_days,
            "inactive_seeker_days": settings.retention_inactive_seeker_days,
        },
    }


def _task_out(t: BackgroundTask) -> AdminTask:
    return AdminTask(
        id=t.id,
        kind=t.kind,
        status=t.status,
        attempts=t.attempts,
        error=t.error,
        ref_type=t.ref_type,
        ref_id=t.ref_id,
        created_at=t.created_at,
        finished_at=t.finished_at,
    )


@router.post("/retention/run")
def run_retention_now(admin: User = Depends(admin_only)):
    from app.tasks.definitions import retention_sweep
    from app.tasks.tracking import enqueue

    return {"task_id": enqueue(retention_sweep, user_id=admin.id)}


# ---------- applications ----------


@router.get("/applications")
def list_applications(
    q: str = Query("", max_length=100),
    status: ApplicationStatus | None = None,
    sort: str = Query("applied_at", pattern="^(candidate|job_title|company|status|applied_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    seeker = aliased(User)
    stmt = (
        select(
            Application.id,
            seeker.full_name,
            seeker.email,
            Job.title,
            Company.name,
            Application.status,
            Application.applied_at,
        )
        .join(seeker, seeker.id == Application.seeker_id)
        .join(Job, Job.id == Application.job_id)
        .join(Company, Company.id == Job.company_id)
    )
    if q.strip():
        pattern = _like(q.strip())
        stmt = stmt.where(
            or_(
                seeker.full_name.ilike(pattern, escape="\\"),
                seeker.email.ilike(pattern, escape="\\"),
                Job.title.ilike(pattern, escape="\\"),
                Company.name.ilike(pattern, escape="\\"),
            )
        )
    if status:
        stmt = stmt.where(Application.status == status)
    columns = {
        "candidate": seeker.full_name,
        "job_title": Job.title,
        "company": Company.name,
        "status": Application.status,
        "applied_at": Application.applied_at,
    }
    stmt = stmt.order_by(*_order(columns[sort], order, Application.id))
    return _page(
        db,
        stmt,
        page,
        lambda r: AdminApplication(
            id=r[0],
            candidate=r[1],
            candidate_email=r[2],
            job_title=r[3],
            company=r[4],
            status=r[5].value,
            applied_at=r[6],
        ),
    )
