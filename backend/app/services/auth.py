import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import RecruiterProfile, RefreshToken, SeekerProfile, User
from app.models.enums import UserRole
from app.schemas.auth import RegisterIn
from app.services.companies import get_or_create_company


class EmailTakenError(Exception):
    pass


def register_user(db: Session, data: RegisterIn) -> User:
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise EmailTakenError
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole(data.role),
    )
    db.add(user)
    db.flush()
    if user.role == UserRole.seeker:
        db.add(SeekerProfile(user_id=user.id))
    else:
        company = get_or_create_company(db, data.company_name or "")
        db.add(RecruiterProfile(user_id=user.id, company_id=company.id))
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        # Spend the same time hashing so response time does not reveal which emails exist.
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def issue_tokens(db: Session, user: User, family_id: uuid.UUID | None = None) -> tuple[str, str]:
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id, family_id)
    db.add(
        RefreshToken(
            id=refresh.jti,
            user_id=user.id,
            family_id=refresh.family_id,
            token_hash=hash_token(refresh.token),
            expires_at=refresh.expires_at,
        )
    )
    db.commit()
    return access, refresh.token


def rotate_refresh_token(db: Session, token: str) -> tuple[User, str, str]:
    """Exchange a refresh token for a new pair. Reusing an old token revokes its whole family."""
    payload = decode_token(token, "refresh")
    row = db.get(RefreshToken, uuid.UUID(payload["jti"]))
    if row is None or row.token_hash != hash_token(token):
        raise TokenError("Unknown refresh token")
    if row.revoked_at is not None:
        revoke_family(db, row.family_id)
        raise TokenError("Refresh token reuse detected")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise TokenError("User not found or deactivated")
    row.revoked_at = datetime.now(UTC)
    access, new_refresh = issue_tokens(db, user, family_id=row.family_id)
    return user, access, new_refresh


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    db.commit()


def revoke_token(db: Session, token: str) -> None:
    try:
        payload = decode_token(token, "refresh")
    except TokenError:
        return
    revoke_family(db, uuid.UUID(payload["fam"]))


_DUMMY_HASH = hash_password("not-a-real-password-1")
