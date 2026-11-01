import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.skills import get_taxonomy
from app.models import Resume, SeekerProfile, User
from app.models.enums import UserRole
from app.services.matching import ensure_resume_derived
from app.services.resume_parser import (
    ALLOWED,
    InvalidResumeFile,
    detect_kind,
    extract_text,
    parse_resume,
)
from app.services.storage import get_storage


def _safe_filename(name: str) -> str:
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    return re.sub(r"[^\w.\- ()]", "_", name)[:255] or "resume"


def upload_resume(
    db: Session, user: User, filename: str, content_type: str | None, data: bytes
) -> Resume:
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise InvalidResumeFile(f"File is larger than {settings.max_upload_mb} MB")
    if not data:
        raise InvalidResumeFile("File is empty")
    kind = detect_kind(filename, content_type, data)
    text = extract_text(data, kind)
    parsed = parse_resume(text)
    mime = ALLOWED["." + kind]
    key = f"resumes/{user.id}/{uuid.uuid4().hex}.{kind}"
    get_storage().save(key, data, mime)
    resume = Resume(
        user_id=user.id,
        storage_key=key,
        original_filename=_safe_filename(filename),
        mime_type=mime,
        size_bytes=len(data),
        raw_text=text,
        parsed=parsed.to_dict(),
        skills=parsed.skills,
        years_experience=(
            Decimal(str(parsed.years_experience)) if parsed.years_experience is not None else None
        ),
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def get_own_resume(db: Session, user: User, resume_id: int) -> Resume:
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    return resume


def current_resume(db: Session, user_id: int) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.user_id == user_id, Resume.is_current.is_(True)))


def confirm_resume(
    db: Session, user: User, resume: Resume, skills: list[str], years: float | None
) -> Resume:
    """Seeker reviewed the parsed fields: save edits and make this the current resume."""
    resume.skills = get_taxonomy().normalise(skills)[:60]
    resume.years_experience = Decimal(str(years)) if years is not None else None
    # Unset the old current resume first so the partial unique index is never violated.
    db.execute(
        update(Resume)
        .where(Resume.user_id == user.id, Resume.id != resume.id, Resume.is_current.is_(True))
        .values(is_current=False)
    )
    db.flush()
    resume.is_current = True
    resume.confirmed_at = datetime.now(UTC)

    profile = db.get(SeekerProfile, user.id)
    if profile is None:
        profile = SeekerProfile(user_id=user.id)
        db.add(profile)
    profile.years_experience = resume.years_experience
    parsed = resume.parsed or {}
    if not profile.phone and parsed.get("phone"):
        profile.phone = parsed["phone"]
    if not profile.current_location and parsed.get("location"):
        profile.current_location = parsed["location"]
    db.commit()
    db.refresh(resume)
    on_resume_confirmed(db, resume)
    return resume


def on_resume_confirmed(db: Session, resume: Resume) -> None:
    """Embedding + predicted role category, computed once the seeker confirms."""
    ensure_resume_derived(db, resume)


def can_view_resume_file(db: Session, viewer: User, resume: Resume) -> bool:
    return viewer.role == UserRole.admin or viewer.id == resume.user_id
