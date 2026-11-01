from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.rate_limit import FixedWindowLimiter
from app.core.security import TokenError
from app.db.session import get_db
from app.models import User
from app.schemas.auth import CompanyBrief, LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE = "hike_refresh"
login_limiter = FixedWindowLimiter(
    "login", settings.login_rate_limit, settings.login_rate_window_seconds
)


def user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    if user.recruiter_profile and user.recruiter_profile.company:
        out.company = CompanyBrief.model_validate(user.recruiter_profile.company)
    return out


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/api/auth",
    )


def _token_response(response: Response, user: User, access: str, refresh: str) -> TokenOut:
    _set_refresh_cookie(response, refresh)
    return TokenOut(
        access_token=access, expires_in=settings.access_token_minutes * 60, user=user_out(user)
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, response: Response, db: Session = Depends(get_db)):
    try:
        user = auth_service.register_user(db, data)
    except auth_service.EmailTakenError as e:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists"
        ) from e
    access, refresh = auth_service.issue_tokens(db, user)
    return _token_response(response, user, access, refresh)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    identity = f"{data.email.lower()}:{_client_ip(request)}"
    retry = login_limiter.retry_after(identity)
    if retry:
        minutes = (retry + 59) // 60
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many failed attempts. Try again in {minutes} min.",
            headers={"Retry-After": str(retry)},
        )
    user = auth_service.authenticate(db, data.email, data.password)
    if user is None:
        login_limiter.hit(identity)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")
    login_limiter.reset(identity)
    user.last_login_at = datetime.now(UTC)
    access, refresh = auth_service.issue_tokens(db, user)
    return _token_response(response, user, access, refresh)


@router.post("/refresh", response_model=TokenOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token")
    try:
        user, access, new_refresh = auth_service.rotate_refresh_token(db, token)
    except TokenError as e:
        response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return _token_response(response, user, access, new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        auth_service.revoke_token(db, token)
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)
