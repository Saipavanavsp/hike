"""Data retention policy, applied daily by the worker (or on demand by an admin).

    RETENTION_UNCONFIRMED_DAYS    uploads never reviewed/saved, or that failed to parse
    RETENTION_OLD_RESUME_DAYS     superseded resumes (not the seeker's current one)
    RETENTION_INACTIVE_SEEKER_DAYS seeker accounts with no login for this long (0 = keep)

A rule set to 0 is off. Deleting a resume removes the stored file, extracted text,
embedding and cached match scores; applications made with it stay but lose the link.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Resume, User
from app.models.enums import UserRole
from app.services.resumes import _delete_files

log = logging.getLogger(__name__)
BATCH = 500


def _delete_resumes(db: Session, where) -> int:
    rows = db.execute(select(Resume.id, Resume.storage_key).where(where).limit(BATCH)).all()
    if not rows:
        return 0
    for rid, _ in rows:
        db.delete(db.get(Resume, rid))
    db.commit()
    _delete_files([key for _, key in rows])
    return len(rows)


def run_retention(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    out = {"unconfirmed_resumes": 0, "old_resumes": 0, "inactive_seekers": 0}

    if settings.retention_unconfirmed_days > 0:
        cutoff = now - timedelta(days=settings.retention_unconfirmed_days)
        out["unconfirmed_resumes"] = _delete_resumes(
            db,
            and_(
                Resume.created_at < cutoff,
                Resume.is_current.is_(False),
                or_(Resume.confirmed_at.is_(None), Resume.status == "failed"),
            ),
        )

    if settings.retention_old_resume_days > 0:
        cutoff = now - timedelta(days=settings.retention_old_resume_days)
        out["old_resumes"] = _delete_resumes(
            db,
            and_(
                Resume.is_current.is_(False),
                Resume.confirmed_at.is_not(None),
                Resume.created_at < cutoff,
            ),
        )

    if settings.retention_inactive_seeker_days > 0:
        cutoff = now - timedelta(days=settings.retention_inactive_seeker_days)
        stale = list(
            db.scalars(
                select(User)
                .where(
                    User.role == UserRole.seeker,
                    func.coalesce(User.last_login_at, User.created_at) < cutoff,
                )
                .limit(BATCH)
            )
        )
        for user in stale:
            keys = list(db.scalars(select(Resume.storage_key).where(Resume.user_id == user.id)))
            db.delete(user)
            db.commit()
            _delete_files(keys)
        out["inactive_seekers"] = len(stale)

    log.info("retention sweep finished", extra=out)
    return out
