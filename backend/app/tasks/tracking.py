"""Tracked background tasks: a background_tasks row per job, retries with backoff, alerts,
and a dead-letter queue: tasks that are still "failed" after every retry stay in the table
until an admin retries them (requeue) from the System page.

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
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

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


# kind -> task, for requeueing dead-lettered tasks by name.
REGISTRY: dict[str, object] = {}


def tracked(
    kind: str,
    ref_type: str | None = None,
    on_give_up: Callable[..., None] | None = None,
    before_requeue: Callable[..., None] | None = None,
) -> Callable:
    """on_give_up(*args, error) runs once retries are exhausted, e.g. to flag the record.
    before_requeue(*args) runs when an admin retries a dead-lettered task, e.g. to reset it."""

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
        task.before_requeue = before_requeue
        REGISTRY[kind] = task
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


STALE_AFTER = timedelta(minutes=10)


def recover_stale_tasks(now: datetime | None = None) -> int:
    """Re-dispatch tasks left behind by a worker that died (or a lost broker message).

    Runs when a worker starts. A task still "queued" or "running" ten minutes after it was
    last touched is sent again under the same id. Every task is idempotent, so a task that
    was in fact still running elsewhere does no harm when it runs twice.
    """
    from sqlalchemy import and_, or_

    now = now or datetime.now(UTC)
    cutoff = now - STALE_AFTER
    with SessionLocal() as db:
        stale = list(
            db.scalars(
                select(BackgroundTask).where(
                    or_(
                        and_(BackgroundTask.status == "queued", BackgroundTask.created_at < cutoff),
                        and_(
                            BackgroundTask.status.in_(("running", "retrying")),
                            func.coalesce(BackgroundTask.started_at, BackgroundTask.created_at)
                            < cutoff,
                        ),
                    )
                )
            )
        )
        jobs = [(t.id, t.kind, list(t.args or [])) for t in stale]
    sent = 0
    for task_id, kind, args in jobs:
        task = REGISTRY.get(kind)
        if task is None:
            continue
        task.apply_async(args=args, task_id=task_id)
        sent += 1
    if sent:
        log.warning("recovered %d stale background task(s)", sent)
    return sent


class NotRetryable(ValueError):
    pass


def requeue(task_id: str, user_id: int | None = None) -> str:
    """Retry a dead-lettered task: a "failed" task (retries exhausted) is queued again as a
    new task with the same arguments, and the old row records which task replaced it."""
    with SessionLocal() as db:
        row = db.get(BackgroundTask, task_id)
        if row is None:
            raise NotRetryable("Task not found")
        if row.status != "failed":
            raise NotRetryable("Only failed tasks can be retried")
        if (row.result or {}).get("retried_as"):
            raise NotRetryable("This task was already retried")
        task = REGISTRY.get(row.kind)
        if task is None:
            raise NotRetryable(f"Unknown task kind {row.kind}")
        args, ref_id = list(row.args or []), row.ref_id
    if task.before_requeue is not None:
        task.before_requeue(*args)
    new_id = enqueue(task, *args, user_id=user_id, ref_id=ref_id)
    with SessionLocal() as db:
        row = db.get(BackgroundTask, task_id)
        row.result = {**(row.result or {}), "retried_as": new_id}
        db.commit()
    log.info("dead-lettered task requeued", extra={"task_id": task_id, "new_task_id": new_id})
    return new_id
