from datetime import timedelta

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.auth import REFRESH_COOKIE
from app.core.deps import require_role
from app.core.security import create_access_token, create_refresh_token
from tests.factories import PASSWORD, login, make_user


def use_refresh_cookie(client, token):
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, token)


def register(client, **overrides):
    body = {
        "email": "asha@example.com",
        "password": "Secret123",
        "full_name": "Asha Rao",
        "role": "seeker",
    }
    body.update(overrides)
    return client.post("/api/auth/register", json=body)


def test_register_seeker_returns_tokens_and_cookie(client):
    res = register(client)
    assert res.status_code == 201
    data = res.json()
    assert data["user"]["role"] == "seeker"
    assert data["access_token"]
    assert REFRESH_COOKIE in res.cookies
    assert "password_hash" not in data["user"]


def test_register_recruiter_requires_company(client):
    res = register(client, role="recruiter")
    assert res.status_code == 422
    res = register(client, role="recruiter", company_name="Tidepool Labs")
    assert res.status_code == 201
    assert res.json()["user"]["company"]["name"] == "Tidepool Labs"


def test_register_cannot_choose_admin(client):
    assert register(client, role="admin").status_code == 422


def test_register_duplicate_email_is_conflict(client):
    assert register(client).status_code == 201
    assert register(client, email="ASHA@example.com").status_code == 409


def test_register_rejects_weak_password(client):
    assert register(client, password="short").status_code == 422
    assert register(client, password="onlyletters").status_code == 422


def test_login_and_me(client, db):
    make_user(db, "ravi@example.com")
    headers = login(client, "ravi@example.com")
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "ravi@example.com"


def test_login_wrong_password_is_401(client, db):
    make_user(db, "ravi@example.com")
    res = client.post("/api/auth/login", json={"email": "ravi@example.com", "password": "nope1234"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password"


def test_login_unknown_email_is_401(client):
    res = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "x1"})
    assert res.status_code == 401


def test_login_rate_limited_after_5_failures(client, db):
    make_user(db, "ravi@example.com")
    bad = {"email": "ravi@example.com", "password": "wrong-pass1"}
    for _ in range(5):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    res = client.post("/api/auth/login", json=bad)
    assert res.status_code == 429
    assert int(res.headers["Retry-After"]) > 0
    # Even the right password is blocked until the window passes.
    good = {"email": "ravi@example.com", "password": PASSWORD}
    assert client.post("/api/auth/login", json=good).status_code == 429


def test_successful_login_resets_failure_count(client, db):
    make_user(db, "ravi@example.com")
    bad = {"email": "ravi@example.com", "password": "wrong-pass1"}
    for _ in range(4):
        client.post("/api/auth/login", json=bad)
    login(client, "ravi@example.com")
    for _ in range(4):
        assert client.post("/api/auth/login", json=bad).status_code == 401


def test_deactivated_user_cannot_login(client, db):
    make_user(db, "old@example.com", is_active=False)
    res = client.post("/api/auth/login", json={"email": "old@example.com", "password": PASSWORD})
    assert res.status_code == 403


def test_me_without_token_is_401(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"


def test_expired_access_token_is_401(client, db):
    user = make_user(db, "ravi@example.com")
    token = create_access_token(user.id, "seeker", expires_delta=timedelta(seconds=-5))
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Token expired"


def test_refresh_token_cannot_be_used_as_access_token(client, db):
    user = make_user(db, "ravi@example.com")
    token = create_refresh_token(user.id).token
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_refresh_rotates_and_detects_reuse(client, db):
    make_user(db, "ravi@example.com")
    login(client, "ravi@example.com")
    first = client.cookies.get(REFRESH_COOKIE)

    res = client.post("/api/auth/refresh")
    assert res.status_code == 200
    second = client.cookies.get(REFRESH_COOKIE)
    assert second and second != first

    # Replaying the first (already rotated) token is treated as theft: whole family revoked.
    use_refresh_cookie(client, first)
    assert client.post("/api/auth/refresh").status_code == 401
    use_refresh_cookie(client, second)
    assert client.post("/api/auth/refresh").status_code == 401


def test_expired_refresh_token_is_401(client, db):
    user = make_user(db, "ravi@example.com")
    token = create_refresh_token(user.id, expires_delta=timedelta(seconds=-1)).token
    use_refresh_cookie(client, token)
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_refresh_token(client, db):
    make_user(db, "ravi@example.com")
    login(client, "ravi@example.com")
    token = client.cookies.get(REFRESH_COOKIE)
    assert client.post("/api/auth/logout").status_code == 204
    use_refresh_cookie(client, token)
    assert client.post("/api/auth/refresh").status_code == 401


def test_require_role_denies_with_403(db):
    app = FastAPI()

    @app.get("/recruiters-only")
    def recruiters_only(_=Depends(require_role("recruiter"))):
        return {"ok": True}

    from app.api.auth import router as auth_router

    app.include_router(auth_router)
    with TestClient(app, headers={"X-CSRF-Protection": "1"}) as c:
        make_user(db, "seeker@example.com", "seeker")
        make_user(db, "rec@example.com", "recruiter")
        assert c.get("/recruiters-only").status_code == 401
        assert c.get("/recruiters-only", headers=login(c, "seeker@example.com")).status_code == 403
        assert c.get("/recruiters-only", headers=login(c, "rec@example.com")).status_code == 200
