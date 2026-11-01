import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: int, role: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    exp = now + (expires_delta or timedelta(minutes=settings.access_token_minutes))
    payload = {"sub": str(user_id), "role": role, "type": "access", "iat": now, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@dataclass
class RefreshTokenData:
    token: str
    jti: uuid.UUID
    family_id: uuid.UUID
    expires_at: datetime


def create_refresh_token(
    user_id: int, family_id: uuid.UUID | None = None, expires_delta: timedelta | None = None
) -> RefreshTokenData:
    now = datetime.now(UTC)
    exp = now + (expires_delta or timedelta(days=settings.refresh_token_days))
    jti = uuid.uuid4()
    family = family_id or uuid.uuid4()
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(jti),
        "fam": str(family),
        "iat": now,
        "exp": exp,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return RefreshTokenData(token=token, jti=jti, family_id=family, expires_at=exp)


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as e:
        raise TokenError("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenError("Invalid token") from e
    if payload.get("type") != expected_type:
        raise TokenError("Wrong token type")
    return payload
