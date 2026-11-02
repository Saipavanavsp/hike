"""Redis helpers. Every call degrades gracefully: if Redis is down we just skip the cache."""

import json
import logging
from typing import Any

from prometheus_client import Counter

from app.core.redis import get_redis

log = logging.getLogger(__name__)

JOBS_VERSION_KEY = "jobs:version"


def jobs_version() -> int:
    """Monotonic counter bumped on every job write. Cache keys embed it, so one INCR
    invalidates every cached search at once (old keys simply expire)."""
    try:
        return int(get_redis().get(JOBS_VERSION_KEY) or 0)
    except Exception:
        log.warning("redis unavailable: jobs_version")
        return -1


def bump_jobs_version() -> None:
    try:
        get_redis().incr(JOBS_VERSION_KEY)
    except Exception:
        log.warning("redis unavailable: bump_jobs_version")


CACHE_REQUESTS = Counter(
    "hike_cache_requests_total",
    "Redis cache lookups by cache (key prefix) and result.",
    ["cache", "result"],
)


def _cache_name(key: str) -> str:
    return key.split(":", 1)[0]


def get_json(key: str) -> Any | None:
    try:
        raw = get_redis().get(key)
    except Exception:
        CACHE_REQUESTS.labels(_cache_name(key), "error").inc()
        return None
    CACHE_REQUESTS.labels(_cache_name(key), "hit" if raw else "miss").inc()
    return json.loads(raw) if raw else None


def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    try:
        get_redis().set(key, json.dumps(value), ex=ttl_seconds)
    except Exception:
        log.warning("redis unavailable: set_json")
