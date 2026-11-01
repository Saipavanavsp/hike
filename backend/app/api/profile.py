import re
from decimal import Decimal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models import SeekerProfile, User
from app.services import resumes as resume_service

router = APIRouter(prefix="/api/profile", tags=["profile"])
account_router = APIRouter(prefix="/api/account", tags=["account"])
seeker_only = require_role("seeker")

PHONE_RE = re.compile(r"^\+?[0-9][0-9 -]{7,15}$")


class ProfileOut(BaseModel):
    full_name: str
    email: str
    headline: str | None
    current_location: str | None
    preferred_locations: list[str]
    open_to_remote: bool
    years_experience: float | None
    phone: str | None


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    headline: str | None = Field(default=None, max_length=160)
    current_location: str | None = Field(default=None, max_length=80)
    preferred_locations: list[str] | None = Field(default=None, max_length=10)
    open_to_remote: bool | None = None
    years_experience: float | None = Field(default=None, ge=0, le=50)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if not PHONE_RE.match(v):
            raise ValueError("Enter a valid phone number, e.g. +91 98765 43210")
        return v

    @field_validator("preferred_locations")
    @classmethod
    def _locations(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out: list[str] = []
        for loc in v:
            loc = " ".join(loc.split())[:80]
            if loc and loc.lower() not in {o.lower() for o in out}:
                out.append(loc)
        return out


def _out(user: User, p: SeekerProfile) -> ProfileOut:
    return ProfileOut(
        full_name=user.full_name,
        email=user.email,
        headline=p.headline,
        current_location=p.current_location,
        preferred_locations=list(p.preferred_locations or []),
        open_to_remote=p.open_to_remote,
        years_experience=float(p.years_experience) if p.years_experience is not None else None,
        phone=p.phone,
    )


def _profile(db: Session, user: User) -> SeekerProfile:
    p = db.get(SeekerProfile, user.id)
    if p is None:
        p = SeekerProfile(user_id=user.id, preferred_locations=[], open_to_remote=True)
        db.add(p)
        db.commit()
    return p


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db), user: User = Depends(seeker_only)):
    return _out(user, _profile(db, user))


class DeleteAccountIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


@account_router.post("/delete", status_code=204)
def delete_account(
    data: DeleteAccountIn,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Permanently erase a seeker's account and all of their data. Requires the password."""
    resume_service.delete_account(db, user, data.password)
    response.delete_cookie("hike_refresh", path="/api/auth")
    response.status_code = 204
    return None


@router.put("", response_model=ProfileOut)
def update_profile(
    data: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(seeker_only)
):
    p = _profile(db, user)
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes and changes["full_name"]:
        user.full_name = changes.pop("full_name").strip()
    changes.pop("full_name", None)
    if "years_experience" in changes and changes["years_experience"] is not None:
        changes["years_experience"] = Decimal(str(changes["years_experience"]))
    for k, v in changes.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _out(user, p)
