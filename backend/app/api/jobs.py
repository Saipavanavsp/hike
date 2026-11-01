from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.deps import get_optional_user, require_role
from app.db.session import get_db
from app.models import Job, SavedJob, User
from app.models.enums import RemoteType, RoleCategory, UserRole
from app.schemas.jobs import (
    JobDetail,
    JobListItem,
    JobPage,
    MatchBreakdown,
    SavedJobItem,
    Suggestion,
)
from app.services import search as search_service
from app.services.autocomplete import index as autocomplete_index
from app.services.jobs import get_job_or_404
from app.services.matching import get_match_results, match_one
from app.services.resumes import current_resume

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def seeker_match_context(db: Session, user: User | None):
    """(match_lookup, resume_category) for a seeker with a resume; (None, None) otherwise."""
    if user is None or user.role != UserRole.seeker:
        return None, None
    resume = current_resume(db, user.id)
    if resume is None:
        return None, None

    def lookup(job_ids: list[int]) -> dict[int, int]:
        return {jid: b["score"] for jid, b in get_match_results(db, resume, job_ids).items()}

    category = resume.predicted_category.value if resume.predicted_category else None
    return lookup, category


def job_detail_extras(db: Session, user: User | None, job: Job, detail: JobDetail) -> None:
    """Fill per-user fields (match breakdown, application status) on a job detail."""
    if user is None or user.role != UserRole.seeker:
        return
    resume = current_resume(db, user.id)
    if resume is not None:
        breakdown = match_one(db, resume, job.id)
        if breakdown:
            detail.match = MatchBreakdown(**breakdown)
            detail.match_score = breakdown["score"]


@router.get("", response_model=JobPage)
def list_jobs(
    q: str = Query("", max_length=200),
    location: list[str] = Query(default=[]),
    role: list[RoleCategory] = Query(default=[]),
    remote: list[RemoteType] = Query(default=[]),
    experience: int | None = Query(None, ge=0, le=40),
    salary_min: int | None = Query(None, ge=0),
    salary_max: int | None = Query(None, ge=0),
    sort: str = Query("relevance", pattern="^(relevance|newest|salary|match)$"),
    page: int = Query(1, ge=1, le=500),
    page_size: int = Query(search_service.PAGE_SIZE, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    params = search_service.SearchParams(
        q=q,
        locations=location,
        roles=[r.value for r in role],
        remote=[r.value for r in remote],
        experience=experience,
        salary_min=salary_min,
        salary_max=salary_max,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    lookup, category = seeker_match_context(db, user)
    result = search_service.search_jobs(db, params, lookup, category)
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_(result.job_ids)))}
    items = []
    for jid in result.job_ids:
        item = JobListItem.model_validate(jobs[jid])
        item.match_score = result.match_scores.get(jid)
        items.append(item)
    return JobPage(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
    )


@router.get("/autocomplete", response_model=list[Suggestion])
def autocomplete(
    q: str = Query(..., min_length=1, max_length=60),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return autocomplete_index.suggest(db, q, limit)


@router.get("/saved", response_model=list[SavedJobItem])
def saved_jobs(db: Session = Depends(get_db), user: User = Depends(require_role("seeker"))):
    rows = db.execute(
        select(Job, SavedJob.saved_at)
        .join(SavedJob, SavedJob.job_id == Job.id)
        .where(SavedJob.user_id == user.id)
        .order_by(SavedJob.saved_at.desc())
    ).all()
    lookup, _ = seeker_match_context(db, user)
    scores = lookup([j.id for j, _ in rows]) if lookup else {}
    out = []
    for job, saved_at in rows:
        item = SavedJobItem.model_validate(
            {**JobListItem.model_validate(job).model_dump(), "saved_at": saved_at}
        )
        item.match_score = scores.get(job.id)
        out.append(item)
    return out


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
):
    job = get_job_or_404(db, job_id)
    detail = JobDetail.model_validate(job)
    if user and user.role == UserRole.seeker:
        detail.is_saved = (
            db.scalar(
                select(SavedJob.job_id).where(
                    SavedJob.user_id == user.id, SavedJob.job_id == job.id
                )
            )
            is not None
        )
    job_detail_extras(db, user, job, detail)
    return detail


@router.post("/{job_id}/save", status_code=status.HTTP_204_NO_CONTENT)
def save_job(
    job_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("seeker"))
):
    get_job_or_404(db, job_id)
    db.execute(insert(SavedJob).values(user_id=user.id, job_id=job_id).on_conflict_do_nothing())
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{job_id}/save", status_code=status.HTTP_204_NO_CONTENT)
def unsave_job(
    job_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("seeker"))
):
    row = db.get(SavedJob, (user.id, job_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job is not saved")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
