from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole

bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Returns the user for a valid token, None when no token is sent, 401 for a bad token."""
    if creds is None:
        return None
    try:
        payload = decode_token(creds.credentials, "access")
    except TokenError as e:
        raise _unauthorized(str(e)) from e
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise _unauthorized("User not found or deactivated")
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    # 401 = we don't know who you are.
    if user is None:
        raise _unauthorized("Not authenticated")
    return user


def require_role(*roles: str | UserRole) -> Callable[..., User]:
    allowed = {UserRole(r) for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        # 403 = we know who you are, but you may not do this.
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "You do not have access to this resource"
            )
        return user

    return checker
