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
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], (b"x-request-id", rid.encode())]
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
