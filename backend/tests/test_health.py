def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "ok", "redis": "ok"}


def test_health_under_api_prefix(client):
    assert client.get("/api/health").status_code == 200
