"""Dependency checks shared by /health, /metrics and the admin system page."""

import time
from datetime import UTC, datetime, timedelta

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import SessionLocal
from app.models import BackgroundTask
from app.models.task import TASK_STATUSES

HEARTBEAT_KEY = "hike:worker:heartbeat"
QUEUE_NAME = "celery"


def check_db() -> tuple[bool, float]:
    t0 = time.perf_counter()
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        ok = True
    except Exception:
        ok = False
    return ok, round((time.perf_counter() - t0) * 1000, 1)


def check_redis() -> tuple[bool, float]:
    t0 = time.perf_counter()
    try:
        ok = bool(get_redis().ping())
    except Exception:
        ok = False
    return ok, round((time.perf_counter() - t0) * 1000, 1)


def worker_status() -> str:
    """Returns inline (tasks run in the API process), or ok / down from the worker heartbeat."""
    if settings.tasks_eager:
        return "inline"
    try:
        beat = get_redis().get(HEARTBEAT_KEY)
    except Exception:
        return "down"
    return "ok" if beat and time.time() - int(beat) < 90 else "down"


def queue_depth() -> int | None:
    if settings.tasks_eager:
        return 0
    try:
        return int(get_redis().llen(QUEUE_NAME))
    except Exception:
        return None


def task_counts(hours: int = 24) -> dict[str, int]:
    since = datetime.now(UTC) - timedelta(hours=hours)
    with SessionLocal() as db:
        rows = db.execute(
            select(BackgroundTask.status, func.count())
            .where(BackgroundTask.created_at >= since)
            .group_by(BackgroundTask.status)
        ).all()
    counts = {s: 0 for s in TASK_STATUSES}
    counts.update({s: n for s, n in rows})
    return counts


class DependencyCollector(Collector):
    """Computed at scrape time, so the numbers are right however many processes exist."""

    def collect(self):
        up = GaugeMetricFamily(
            "hike_dependency_up", "1 if the dependency answered a health check.", labels=["name"]
        )
        latency = GaugeMetricFamily(
            "hike_dependency_latency_ms", "Health check round trip.", labels=["name"]
        )
        for name, check in (("postgres", check_db), ("redis", check_redis)):
            ok, ms = check()
            up.add_metric([name], 1.0 if ok else 0.0)
            latency.add_metric([name], ms)
        yield up
        yield latency

        yield GaugeMetricFamily(
            "hike_worker_up",
            "1 if a background worker sent a heartbeat in the last 90s (or tasks run inline).",
            value=0.0 if worker_status() == "down" else 1.0,
        )
        depth = queue_depth()
        if depth is not None:
            yield GaugeMetricFamily("hike_queue_depth", "Tasks waiting in the queue.", value=depth)
        try:
            counts = task_counts(hours=1)
        except Exception:
            return
        tasks = GaugeMetricFamily(
            "hike_background_tasks_last_hour",
            "Background tasks created in the last hour, by current status.",
            labels=["status"],
        )
        for status, n in counts.items():
            tasks.add_metric([status], n)
        yield tasks
        with SessionLocal() as db:
            dead = db.scalar(
                select(func.count())
                .select_from(BackgroundTask)
                .where(
                    BackgroundTask.status == "failed",
                    func.coalesce(BackgroundTask.result.op("->>")("retried_as"), "") == "",
                )
            )
        yield GaugeMetricFamily(
            "hike_dead_letter_tasks",
            "Tasks that failed after every retry and have not been retried by an admin.",
            value=dead,
        )
