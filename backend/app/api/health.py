from fastapi import APIRouter, Header, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import settings
from app.core.health import check_db, check_redis, queue_depth, worker_status

router = APIRouter(tags=["health"])
metrics_router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response) -> dict:
    """Liveness/readiness: 503 if Postgres or Redis is down. The worker is reported but does
    not fail the check, because the API keeps working (tasks queue up) without it."""
    db_ok, db_ms = check_db()
    redis_ok, redis_ms = check_redis()
    healthy = db_ok and redis_ok
    if not healthy:
        response.status_code = 503
    return {
        "status": "ok" if healthy else "degraded",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "worker": worker_status(),
        "queue_depth": queue_depth(),
        "latency_ms": {"db": db_ms, "redis": redis_ms},
    }


@metrics_router.get("/metrics", include_in_schema=False)
def metrics(authorization: str | None = Header(default=None)) -> Response:
    if settings.metrics_token and authorization != f"Bearer {settings.metrics_token}":
        raise HTTPException(401, "Metrics token required")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
