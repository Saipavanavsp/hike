"""Small helpers to create users and log in from tests."""

from app.core.security import hash_password
from app.models import RecruiterProfile, SeekerProfile, User
from app.models.enums import UserRole
from app.services.companies import get_or_create_company

PASSWORD = "Passw0rd!"


def make_user(db, email: str, role: str = "seeker", company: str = "Acme Test Co", **kw) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        full_name=kw.pop("full_name", email.split("@")[0].title()),
        role=UserRole(role),
        **kw,
    )
    db.add(user)
    db.flush()
    if role == "seeker":
        db.add(SeekerProfile(user_id=user.id))
    elif role == "recruiter":
        c = get_or_create_company(db, company)
        db.add(RecruiterProfile(user_id=user.id, company_id=c.id))
    db.commit()
    return user


def login(client, email: str, password: str = PASSWORD) -> dict:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def auth_headers(db, client, email: str, role: str = "seeker", **kw) -> tuple[User, dict]:
    user = make_user(db, email, role, **kw)
    return user, login(client, email)


def post_resume(client, headers, name: str, data: bytes, mime: str, consent: bool = True):
    return client.post(
        "/api/resumes",
        files={"file": (name, data, mime)},
        data={"consent": "true" if consent else "false"},
        headers=headers,
    )


def fetch_resume_file(client, headers, resume_id: int):
    """Request a signed link (authorised), then download through it (no bearer token)."""
    link = client.post(f"/api/resumes/{resume_id}/link", headers=headers)
    if link.status_code != 200:
        return link
    return client.get(link.json()["url"])
