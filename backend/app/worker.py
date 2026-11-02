"""Celery application. Redis is the broker; task status lives in the background_tasks table.

    celery -A app.worker worker --beat --loglevel=INFO --concurrency=2

With TASKS_EAGER=true no worker is needed: tasks run inline in the API process.
"""

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging, task_postrun, task_prerun, worker_ready

from app.core.config import settings
from app.core.observability import configure_logging, init_sentry, request_id_var

celery_app = Celery("hike", broker=settings.redis_url, include=["app.tasks.definitions"])
celery_app.conf.update(
    task_always_eager=settings.tasks_eager,
    task_eager_propagates=False,
    task_ignore_result=True,
    # Acknowledge after the task finishes, so a crashed worker's task is redelivered.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_hijack_root_logger=False,
    broker_connection_retry_on_startup=True,
    # Publishing must fail fast when Redis is down, so the API can fall back to running inline.
    task_publish_retry_policy={
        "max_retries": 2,
        "interval_start": 0,
        "interval_step": 0.5,
        "interval_max": 1,
    },
    # A task taken by a worker that dies is redelivered after this long (acks_late).
    broker_transport_options={"visibility_timeout": 900},
    # On SIGTERM the worker stops taking tasks and finishes the ones it has (warm shutdown);
    # docker-compose gives it stop_grace_period to do so.
    worker_cancel_long_running_tasks_on_connection_loss=True,
    timezone="UTC",
    beat_schedule={
        "worker-heartbeat": {"task": "hike.heartbeat", "schedule": 30.0},
        "retention-sweep": {"task": "hike.retention_sweep", "schedule": crontab(hour=3, minute=0)},
    },
)


@setup_logging.connect
def _setup_logging(**_kwargs) -> None:
    configure_logging()
    init_sentry()


@worker_ready.connect
def _recover(**_kwargs) -> None:
    from app.tasks.tracking import recover_stale_tasks

    try:
        recover_stale_tasks()
    except Exception:  # never block worker start-up
        import logging

        logging.getLogger("hike.tasks").exception("stale task recovery failed")


@task_prerun.connect
def _bind_task_id(task_id=None, task=None, **_kwargs) -> None:
    # Worker log lines carry the task id in the request_id field. Eager tasks run inside an
    # API request and keep that request's id instead.
    if task is not None and not task.request.is_eager:
        request_id_var.set(task_id)


@task_postrun.connect
def _unbind_task_id(task=None, **_kwargs) -> None:
    if task is not None and not task.request.is_eager:
        request_id_var.set(None)
