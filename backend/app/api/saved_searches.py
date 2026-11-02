from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models import SavedSearch, User
from app.models.enums import RemoteType, RoleCategory
from app.services.saved_searches import MAX_PER_USER, describe

router = APIRouter(prefix="/api/saved-searches", tags=["saved searches"])
seeker_only = require_role("seeker")


class SearchFilters(BaseModel):
    q: str = Field("", max_length=200)
    location: list[str] = Field(default_factory=list, max_length=10)
    role: list[RoleCategory] = Field(default_factory=list)
    remote: list[RemoteType] = Field(default_factory=list)
    experience: int | None = Field(default=None, ge=0, le=40)

    @field_validator("q")
    @classmethod
    def _q(cls, v: str) -> str:
        return " ".join(v.split())


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    params: SearchFilters
    alerts_enabled: bool = True


class SavedSearchPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    alerts_enabled: bool | None = None


class SavedSearchOut(BaseModel):
    id: int
    name: str
    params: dict
    summary: str
    alerts_enabled: bool
    last_alert_at: datetime | None
    created_at: datetime


def _out(s: SavedSearch) -> SavedSearchOut:
    return SavedSearchOut(
        id=s.id,
        name=s.name,
        params=s.params,
        summary=describe(s.params),
        alerts_enabled=s.alerts_enabled,
        last_alert_at=s.last_alert_at,
        created_at=s.created_at,
    )


def _own(db: Session, user: User, search_id: int) -> SavedSearch:
    s = db.get(SavedSearch, search_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saved search not found")
    return s


@router.get("", response_model=list[SavedSearchOut])
def list_searches(db: Session = Depends(get_db), user: User = Depends(seeker_only)):
    rows = db.scalars(
        select(SavedSearch)
        .where(SavedSearch.user_id == user.id)
        .order_by(SavedSearch.created_at.desc(), SavedSearch.id.desc())
    )
    return [_out(s) for s in rows]


@router.post("", response_model=SavedSearchOut, status_code=201)
def create_search(
    data: SavedSearchIn, db: Session = Depends(get_db), user: User = Depends(seeker_only)
):
    count = db.scalar(
        select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user.id)
    )
    if count >= MAX_PER_USER:
        raise HTTPException(422, f"You can save up to {MAX_PER_USER} searches")
    s = SavedSearch(
        user_id=user.id,
        name=data.name.strip(),
        params=data.params.model_dump(mode="json"),
        alerts_enabled=data.alerts_enabled,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _out(s)


@router.patch("/{search_id}", response_model=SavedSearchOut)
def update_search(
    search_id: int,
    data: SavedSearchPatch,
    db: Session = Depends(get_db),
    user: User = Depends(seeker_only),
):
    s = _own(db, user, search_id)
    if data.name is not None:
        s.name = data.name.strip()
    if data.alerts_enabled is not None:
        s.alerts_enabled = data.alerts_enabled
    db.commit()
    db.refresh(s)
    return _out(s)


@router.delete("/{search_id}", status_code=204)
def delete_search(search_id: int, db: Session = Depends(get_db), user: User = Depends(seeker_only)):
    db.delete(_own(db, user, search_id))
    db.commit()
    return Response(status_code=204)
