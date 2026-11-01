from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import EvalRun, Job, User
from app.models.enums import JobStatus, UserRole

router = APIRouter(prefix="/api/stats", tags=["stats"])


class PublicStats(BaseModel):
    open_jobs: int
    companies: int
    recruiters: int
    candidates: int
    precision_at_5: float | None
    tfidf_precision_at_5: float | None
    eval_run_at: str | None


@router.get("/public", response_model=PublicStats)
def public_stats(db: Session = Depends(get_db)):
    """Live counts for the landing page. Companies are counted through jobs so companies
    without postings are not shown. Eval numbers come from the latest eval run."""

    def count_users(role: UserRole) -> int:
        return db.scalar(
            select(func.count()).select_from(User).where(User.role == role, User.is_active)
        )

    run = db.scalar(select(EvalRun).order_by(EvalRun.run_at.desc()).limit(1))
    methods = (run.metrics.get("matching", {}).get("methods", {}) if run else {}) or {}
    return PublicStats(
        open_jobs=db.scalar(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.open)
        ),
        companies=db.scalar(select(func.count(func.distinct(Job.company_id)))),
        recruiters=count_users(UserRole.recruiter),
        candidates=count_users(UserRole.seeker),
        precision_at_5=methods.get("hike", {}).get("precision_at_5"),
        tfidf_precision_at_5=methods.get("tfidf", {}).get("precision_at_5"),
        eval_run_at=run.run_at.isoformat() if run else None,
    )
