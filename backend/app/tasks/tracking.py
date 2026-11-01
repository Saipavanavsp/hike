"""Tracked background tasks: a background_tasks row per job, retries with backoff, alerts.

    @tracked("process_resume", ref_type="resume")
    def process_resume(resume_id: int) -> dict: ...

    enqueue(process_resume, resume.id, user_id=user.id, ref_id=resume.id)

Any exception is retried (exponential backoff with jitter, TASK_MAX_RETRIES times) except
PermanentError, which ends the task at once ("rejected", or "failed" if alert=True). A task
that fails for good is logged at ERROR with alert=true, sent to Sentry when configured, and
reported to admins in the app.
"""

import logging
import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.core.observability import capture_exception
from app.core.redis import get_redis
from app.db.session import SessionLocal
from app.models import BackgroundTask, Notification, User
from app.models.enums import UserRole
from app.worker import celery_app

log = logging.getLogger("hike.tasks")


class PermanentError(Exception):
    """Fail without retrying. alert=False for expected outcomes such as an unreadable file."""

    def __init__(self, message: str, alert: bool = False):
        super().__init__(message)
        self.alert = alert


def backoff_seconds(retries: int) -> float:
    return min(300.0, 5.0 * 2**retries) + random.uniform(0, 2)


def _update(task_id: str, **values) -> None:
    with SessionLocal() as db:
        row = db.get(BackgroundTask, task_id)
        if row is None:  # started by the scheduler, not by enqueue()
            row = BackgroundTask(id=task_id, kind=values.pop("kind", "unknown"))
            db.add(row)
        values.pop("kind", None)
        for k, v in values.items():
            setattr(row, k, v)
        db.commit()


def alert_task_failure(kind: str, task_id: str, error: str) -> None:
    log.error(
        "background task failed: %s",
        kind,
        extra={"alert": True, "task_kind": kind, "task_id": task_id, "error": error},
    )
    # One in-app alert per task kind per hour, so a broken dependency does not flood admins.
    try:
        first = get_redis().set(f"hike:alert:task_failed:{kind}", task_id, nx=True, ex=3600)
    except Exception:
        first = True
    if not first:
        return
    with SessionLocal() as db:
        for admin in db.scalars(
            select(User).where(User.role == UserRole.admin, User.is_active.is_(True))
        ):
            db.add(
                Notification(
                    user_id=admin.id,
                    type="task_failed",
                    title=f"Background task failed: {kind}",
                    body=error[:1000],
                    link="/admin/system",
                    payload={"task_id": task_id, "kind": kind},
                )
            )
        db.commit()


def tracked(
    kind: str, ref_type: str | None = None, on_give_up: Callable[..., None] | None = None
) -> Callable:
    """on_give_up(*args, error) runs once retries are exhausted, e.g. to flag the record."""

    def decorator(fn: Callable) -> Callable:
        @celery_app.task(name=f"hike.{kind}", bind=True, max_retries=settings.task_max_retries)
        def task(self, *args):
            task_id = self.request.id
            _update(
                task_id,
                kind=kind,
                status="running",
                attempts=self.request.retries + 1,
                started_at=datetime.now(UTC),
                error=None,
            )
            try:
                result = fn(*args)
            except PermanentError as e:
                # "rejected": the input was refused (e.g. an unreadable file); nothing is broken,
                # so it does not count as a failure in metrics or alerts.
                _update(
                    task_id,
                    status="failed" if e.alert else "rejected",
                    error=str(e),
                    finished_at=datetime.now(UTC),
                )
                if e.alert:
                    alert_task_failure(kind, task_id, str(e))
                return None
            except Exception as e:
                error = f"{type(e).__name__}: {e}"[:2000]
                if self.request.retries < self.max_retries:
                    _update(task_id, status="retrying", error=error)
                    log.warning(
                        "task %s failed, retrying",
                        kind,
                        extra={"task_id": task_id, "attempt": self.request.retries + 1},
                    )
                    raise self.retry(exc=e, countdown=backoff_seconds(self.request.retries)) from e
                _update(task_id, status="failed", error=error, finished_at=datetime.now(UTC))
                capture_exception(e)
                alert_task_failure(kind, task_id, error)
                if on_give_up is not None:
                    try:
                        on_give_up(*args, error)
                    except Exception:
                        log.exception("on_give_up handler failed for %s", kind)
                raise
            _update(task_id, status="succeeded", result=result, finished_at=datetime.now(UTC))
            return result

        task.kind = kind
        task.ref_type = ref_type
        return task

    return decorator


def enqueue(task, *args, user_id: int | None = None, ref_id: int | None = None) -> str:
    """Record the task, then hand it to the queue. Commit related rows before calling this."""
    task_id = uuid.uuid4().hex
    with SessionLocal() as db:
        db.add(
            BackgroundTask(
                id=task_id,
                kind=task.kind,
                args=list(args),
                user_id=user_id,
                ref_type=task.ref_type,
                ref_id=ref_id,
            )
        )
        db.commit()
    try:
        task.apply_async(args=args, task_id=task_id)
    except Exception:
        # Broker unreachable: do the work now instead of losing it.
        log.warning("queue unavailable, running %s inline", task.kind, exc_info=True)
        task.apply(args=args, task_id=task_id)
    return task_id
