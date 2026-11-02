"""Structured logging, request IDs, Prometheus metrics and error tracking.

Every request gets an id (the caller's X-Request-ID if it looks safe, else a new one). The id
is returned in the X-Request-ID header, attached to every log line written while the request
is handled, and included in the body of 500 responses so a user-reported error can be found
in the logs.
"""

import json
import logging
import re
import sys
import time
import traceback
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from prometheus_client import Counter, Gauge, Histogram

from app.core.config import settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# Attributes every LogRecord has; anything else was passed through `extra=` and is logged.
_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            out["request_id"] = rid
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                out[key] = value
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        rid = request_id_var.get()
        return f"{line} [request_id={rid}]" if rid else line


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_format == "json" else TextFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level.upper())
    # Uvicorn's own loggers go through the root handler; its access log is replaced by ours.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers[:] = []
        lg.propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def init_sentry() -> bool:
    """Error tracking is optional: enabled only when SENTRY_DSN is set."""
    if not settings.sentry_dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
    return True


def capture_exception(exc: BaseException) -> None:
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)


# ---------- metrics ----------

HTTP_REQUESTS = Counter(
    "hike_http_requests_total",
    "HTTP requests handled, by route template and status code.",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "hike_http_request_duration_seconds",
    "HTTP request latency by route template.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
HTTP_IN_FLIGHT = Gauge("hike_http_requests_in_progress", "Requests currently being handled.")

# Routes whose successful calls are not access-logged (Docker probes them every few seconds).
_QUIET_ROUTES = {"/health", "/api/health", "/metrics"}
log_access = logging.getLogger("hike.access")
log_error = logging.getLogger("hike.error")


def _route_template(scope: dict) -> str:
    route = scope.get("route")
    # Templates ("/api/jobs/{job_id}") keep metric cardinality bounded; raw paths would not.
    return getattr(route, "path", None) or "unmatched"


REQUESTS_WAITING = Gauge(
    "hike_requests_waiting", "Requests queued for a concurrency slot (load shedding)."
)
REQUESTS_SHED = Counter(
    "hike_requests_shed_total", "Requests rejected with 503 because the server was saturated."
)
_UNLIMITED = ("/health", "/api/health", "/metrics")


class ConcurrencyLimitMiddleware:
    """At most MAX_CONCURRENT_REQUESTS requests run at once; the rest wait on the event loop
    (holding no thread and no database connection) and get 503 + Retry-After if no slot frees
    within REQUEST_QUEUE_TIMEOUT. Health checks and metrics bypass the limit so the service
    stays observable while saturated.

    Without this, a burst larger than the thread pool made worker threads wait for database
    connections held by requests that needed a thread to finish: the 500-user load test
    deadlocked the API until it was restarted.
    """

    def __init__(self, app) -> None:
        self.app = app
        self._slots = None
        self._loop = None

    def _semaphore(self):
        import asyncio

        loop = asyncio.get_running_loop()
        if self._loop is not loop:  # a semaphore belongs to one event loop
            self._slots = asyncio.Semaphore(settings.max_concurrent_requests)
            self._loop = loop
        return self._slots

    async def __call__(self, scope, receive, send):
        import asyncio

        if scope["type"] != "http" or scope.get("path", "").startswith(_UNLIMITED):
            await self.app(scope, receive, send)
            return
        self.slots = self._semaphore()
        REQUESTS_WAITING.inc()
        try:
            await asyncio.wait_for(self.slots.acquire(), settings.request_queue_timeout)
        except TimeoutError:
            REQUESTS_WAITING.dec()
            REQUESTS_SHED.inc()
            body = b'{"detail": "The server is busy. Please try again in a moment."}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 503,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", b"2"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        REQUESTS_WAITING.dec()
        try:
            await self.app(scope, receive, send)
        finally:
            self.slots.release()


_DOCS = ("/api/docs", "/api/openapi.json", "/api/docs/oauth2-redirect")


def security_headers(path: str) -> list[tuple[bytes, bytes]]:
    """Headers added to every API response (a response may set its own value first)."""
    headers = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
        (b"cross-origin-opener-policy", b"same-origin"),
        (b"cross-origin-resource-policy", b"same-origin"),
    ]
    # JSON never needs to run scripts or be framed. Exempt: Swagger UI (loads its own assets)
    # and resume files (a CSP on a PDF can stop the browser's built-in viewer from showing it).
    if not path.startswith(_DOCS) and not path.startswith("/api/files/"):
        headers.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"))
    if settings.cookie_secure:  # HTTPS deployments
        headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
    if path.startswith("/api/auth/"):
        headers.append((b"cache-control", b"no-store"))  # responses carry tokens
    return headers


class ObservabilityMiddleware:
    """Pure ASGI middleware: request id, access log, metrics and a JSON 500 for crashes."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        status_code = 500
        started = False
        t0 = time.perf_counter()
        HTTP_IN_FLIGHT.inc()

        async def send_wrapper(message):
            nonlocal status_code, started
            if message["type"] == "http.response.start":
                started = True
                status_code = message["status"]
                existing = list(message.get("headers") or [])
                present = {k.lower() for k, _ in existing}
                extra = [h for h in security_headers(scope.get("path", "")) if h[0] not in present]
                message["headers"] = [*existing, *extra, (b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            status_code = 500
            log_error.error(
                "unhandled error on %s %s",
                scope.get("method"),
                scope.get("path"),
                extra={"error_type": type(exc).__name__, "trace": traceback.format_exc()},
            )
            capture_exception(exc)
            if not started:
                body = json.dumps({"detail": "Internal server error", "request_id": rid}).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                            (b"x-request-id", rid.encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
        finally:
            elapsed = time.perf_counter() - t0
            HTTP_IN_FLIGHT.dec()
            route = _route_template(scope)
            method = scope.get("method", "")
            HTTP_REQUESTS.labels(method, route, str(status_code)).inc()
            HTTP_LATENCY.labels(method, route).observe(elapsed)
            if not (route in _QUIET_ROUTES and status_code < 400):
                log_access.info(
                    "%s %s %s",
                    method,
                    scope.get("path"),
                    status_code,
                    extra={
                        "method": method,
                        "path": scope.get("path"),
                        "route": route,
                        "status": status_code,
                        "duration_ms": round(elapsed * 1000, 1),
                    },
                )
            request_id_var.reset(token)
