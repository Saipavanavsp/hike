import json
import logging
import time

from app.core import health as health_mod
from app.core.config import settings
from app.core.observability import JsonFormatter, request_id_var
from app.core.redis import get_redis


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok" and body["redis"] == "ok"
    assert body["worker"] == "inline"  # TASKS_EAGER in tests
    assert body["latency_ms"]["db"] >= 0


def test_health_under_api_prefix(client):
    assert client.get("/api/health").status_code == 200


def test_health_503_when_redis_down(client, monkeypatch):
    monkeypatch.setattr("app.api.health.check_redis", lambda: (False, 1.0))
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["status"] == "degraded"
    assert res.json()["redis"] == "error"


def test_worker_status_from_heartbeat(monkeypatch):
    monkeypatch.setattr(settings, "tasks_eager", False)
    assert health_mod.worker_status() == "down"
    get_redis().set(health_mod.HEARTBEAT_KEY, int(time.time()))
    assert health_mod.worker_status() == "ok"
    get_redis().set(health_mod.HEARTBEAT_KEY, int(time.time()) - 300)
    assert health_mod.worker_status() == "down"


def test_request_id_generated_and_echoed(client):
    res = client.get("/api/health")
    rid = res.headers["x-request-id"]
    assert len(rid) == 32
    res = client.get("/api/health", headers={"X-Request-ID": "trace-abc.123"})
    assert res.headers["x-request-id"] == "trace-abc.123"
    # Unsafe values (log injection, huge ids) are replaced.
    res = client.get("/api/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert res.headers["x-request-id"] != "bad id\nwith newline"


def test_unhandled_error_returns_json_500_with_request_id(client, caplog):
    from app.main import app

    @app.get("/api/_test_crash")
    def crash():
        raise RuntimeError("kaboom")

    try:
        with caplog.at_level(logging.ERROR, logger="hike.error"):
            res = client.get("/api/_test_crash", headers={"X-Request-ID": "req-500"})
        assert res.status_code == 500
        assert res.json() == {"detail": "Internal server error", "request_id": "req-500"}
        assert res.headers["x-request-id"] == "req-500"
        assert "kaboom" not in res.text  # no internals leak to the client
        assert any("unhandled error" in r.getMessage() for r in caplog.records)
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != "/api/_test_crash"
        ]


def test_metrics_endpoint(client):
    client.get("/api/jobs/999999")  # a 404 on a templated route
    res = client.get("/metrics")
    assert res.status_code == 200
    text = res.text
    assert 'hike_http_requests_total{method="GET",route="/api/jobs/{job_id}",status="404"}' in text
    assert "hike_http_request_duration_seconds_bucket" in text
    assert 'hike_dependency_up{name="postgres"} 1.0' in text
    assert 'hike_dependency_up{name="redis"} 1.0' in text
    assert "hike_worker_up 1.0" in text
    assert 'hike_background_tasks_last_hour{status="failed"}' in text


def test_load_shedding_returns_503_when_saturated(client, monkeypatch):
    """With every slot taken and no queue time, extra requests are refused fast with 503,
    while health checks still answer."""
    monkeypatch.setattr(settings, "max_concurrent_requests", 0)
    monkeypatch.setattr(settings, "request_queue_timeout", 0.05)
    from app.main import app

    app.middleware_stack = None  # rebuild with the patched settings
    try:
        res = client.get("/api/jobs")
        assert res.status_code == 503
        assert res.headers["retry-after"] == "2"
        assert client.get("/health").status_code == 200
        assert "hike_requests_shed_total 1.0" in client.get("/metrics").text
    finally:
        monkeypatch.undo()
        app.middleware_stack = None


def test_metrics_token(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "s3cret")
    assert client.get("/metrics").status_code == 401
    ok = client.get("/metrics", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200


def test_json_log_lines_carry_request_id_and_extras():
    record = logging.LogRecord("hike.test", logging.INFO, __file__, 1, "hello %s", ("x",), None)
    record.duration_ms = 12.5
    token = request_id_var.set("rid-1")
    try:
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["msg"] == "hello x"
    assert line["request_id"] == "rid-1"
    assert line["duration_ms"] == 12.5
    assert line["level"] == "INFO"
