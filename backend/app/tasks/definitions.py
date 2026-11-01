"""Background tasks. Each opens its own database session; arguments are ids only."""

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.core.health import HEARTBEAT_KEY
from app.core.redis import get_redis
from app.db.session import SessionLocal
from app.models import Application, Job, Resume
from app.services.resume_parser import InvalidResumeFile
from app.tasks.tracking import PermanentError, tracked
from app.worker import celery_app

log = logging.getLogger("hike.tasks")


def _resume_gave_up(resume_id: int, error: str) -> None:
    from app.services.resumes import mark_resume_failed

    with SessionLocal() as db:
        mark_resume_failed(
            db, resume_id, "We could not process this file. Please try uploading it again."
        )


@tracked("process_resume", ref_type="resume", on_give_up=_resume_gave_up)
def process_resume(resume_id: int) -> dict:
    from app.services.resumes import process_resume_file

    with SessionLocal() as db:
        try:
            return process_resume_file(db, resume_id)
        except InvalidResumeFile as e:
            # The file itself is the problem: retrying will not help and nothing is broken.
            raise PermanentError(str(e)) from e


@tracked("derive_resume", ref_type="resume")
def derive_resume(resume_id: int) -> dict:
    """Embedding + predicted role category for a confirmed resume."""
    from app.services.matching import ensure_resume_derived

    with SessionLocal() as db:
        resume = db.scalar(
            select(Resume)
            .options(undefer(Resume.embedding), undefer(Resume.raw_text))
            .where(Resume.id == resume_id)
        )
        if resume is None:
            return {"skipped": "resume deleted"}
        ensure_resume_derived(db, resume)
        return {"category": resume.predicted_category.value if resume.predicted_category else None}


@tracked("embed_job", ref_type="job")
def embed_job(job_id: int) -> dict:
    from app.services.matching import ensure_job_embeddings

    with SessionLocal() as db:
        job = db.scalar(select(Job).options(undefer(Job.embedding)).where(Job.id == job_id))
        if job is None:
            return {"skipped": "job deleted"}
        ensure_job_embeddings(db, [job])
        return {"embedded": True}


@tracked("score_job_candidates", ref_type="job")
def score_job_candidates(job_id: int) -> dict:
    """Bulk matching: refresh cached match scores for every applicant of a job."""
    from app.services.matching import match_one

    with SessionLocal() as db:
        resume_ids = list(
            db.scalars(
                select(Application.resume_id).where(
                    Application.job_id == job_id, Application.resume_id.is_not(None)
                )
            )
        )
        for rid in resume_ids:
            resume = db.get(Resume, rid)
            if resume is not None:
                match_one(db, resume, job_id)
        return {"scored": len(resume_ids)}


@tracked("deliver_email", ref_type="notification")
def deliver_email(notification_id: int) -> dict:
    from app.services.notifications import send_email

    with SessionLocal() as db:
        return send_email(db, notification_id)


@tracked("retention_sweep")
def retention_sweep() -> dict:
    from app.services.retention import run_retention

    with SessionLocal() as db:
        return run_retention(db)


@celery_app.task(name="hike.heartbeat", ignore_result=True)
def heartbeat() -> None:
    """Lets /health and /metrics tell whether a worker is alive (not tracked: runs every 30s)."""
    get_redis().set(HEARTBEAT_KEY, int(time.time()), ex=90)
