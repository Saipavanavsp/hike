"""Resume lifecycle: consented upload -> scan -> encrypted storage -> background parse ->
seeker review -> current resume. Seekers can delete any resume or their whole account."""

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password
from app.ml.skills import get_taxonomy
from app.models import Application, Job, Resume, SeekerProfile, User
from app.models.enums import UserRole
from app.services.file_scan import scan_upload
from app.services.resume_parser import (
    ALLOWED,
    InvalidResumeFile,
    detect_kind,
    extract_text_safely,
    parse_resume,
)
from app.services.storage import get_storage

log = logging.getLogger(__name__)


class ConsentRequired(ValueError):
    pass


def _safe_filename(name: str) -> str:
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    return re.sub(r"[^\w.\- ()]", "_", name)[:255] or "resume"


def upload_resume(
    db: Session,
    user: User,
    filename: str,
    content_type: str | None,
    data: bytes,
    consent: bool,
) -> Resume:
    """Validate, scan and store the file, then queue text extraction and parsing.

    The returned resume has status "processing" (or already "ready"/"failed" when tasks
    run inline). Cheap checks fail the request; parsing problems are reported on the resume.
    """
    if not consent:
        raise ConsentRequired("Please agree to resume processing before uploading")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise InvalidResumeFile(f"File is larger than {settings.max_upload_mb} MB")
    if not data:
        raise InvalidResumeFile("File is empty")
    kind = detect_kind(filename, content_type, data)
    scan = scan_upload(data, kind)  # MalwareDetected / ScannerUnavailable propagate
    mime = ALLOWED["." + kind]
    key = f"resumes/{user.id}/{uuid.uuid4().hex}.{kind}"
    get_storage().save(key, data, mime)
    resume = Resume(
        user_id=user.id,
        storage_key=key,
        original_filename=_safe_filename(filename),
        mime_type=mime,
        size_bytes=len(data),
        status="processing",
        parsed={},
        skills=[],
        consent_at=datetime.now(UTC),
        consent_version=settings.consent_version,
        file_sha256=hashlib.sha256(data).hexdigest(),
        scan_result=scan.summary,
    )
    db.add(resume)
    db.commit()

    from app.tasks.definitions import process_resume
    from app.tasks.tracking import enqueue

    enqueue(process_resume, resume.id, user_id=user.id, ref_id=resume.id)
    db.refresh(resume)
    return resume


def process_resume_file(db: Session, resume_id: int) -> dict:
    """Background step: extract text in the sandbox and parse fields. Idempotent."""
    resume = db.get(Resume, resume_id)
    if resume is None or resume.status != "processing":
        return {"skipped": True}
    data = get_storage().read(resume.storage_key)
    kind = "pdf" if resume.mime_type == ALLOWED[".pdf"] else "docx"
    try:
        text = extract_text_safely(data, kind)
    except InvalidResumeFile as e:
        mark_resume_failed(db, resume_id, str(e))
        raise
    parsed = parse_resume(text)
    resume.raw_text = text
    resume.parsed = parsed.to_dict()
    resume.skills = parsed.skills
    resume.years_experience = (
        Decimal(str(parsed.years_experience)) if parsed.years_experience is not None else None
    )
    resume.status = "ready"
    resume.parse_error = None
    db.commit()
    return {"skills": len(parsed.skills), "chars": len(text)}


def mark_resume_failed(db: Session, resume_id: int, message: str) -> None:
    db.rollback()
    resume = db.get(Resume, resume_id)
    if resume is not None and resume.status == "processing":
        resume.status = "failed"
        resume.parse_error = message[:300]
        db.commit()


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
    if resume.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "This resume has not finished processing")
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
    on_resume_confirmed(resume)
    db.refresh(resume)
    return resume


def on_resume_confirmed(resume: Resume) -> None:
    """Embedding + predicted role category, computed in the background."""
    from app.tasks.definitions import derive_resume
    from app.tasks.tracking import enqueue

    enqueue(derive_resume, resume.id, user_id=resume.user_id, ref_id=resume.id)


def can_view_resume_file(db: Session, viewer: User, resume: Resume) -> bool:
    """Owner, admin, or a recruiter who received an application made with this resume."""
    if not viewer.is_active:
        return False
    if viewer.role == UserRole.admin or viewer.id == resume.user_id:
        return True
    if viewer.role != UserRole.recruiter:
        return False
    return (
        db.scalar(
            select(Application.id)
            .join(Job, Job.id == Application.job_id)
            .where(Application.resume_id == resume.id, Job.recruiter_id == viewer.id)
            .limit(1)
        )
        is not None
    )


# ---------- deletion ----------


def _delete_files(keys: list[str]) -> None:
    storage = get_storage()
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            # The database row is already gone; the retention sweep will not find this file,
            # so log it loudly for manual cleanup.
            log.error("could not delete stored file", extra={"storage_key": key, "alert": True})


def delete_resume(db: Session, resume: Resume) -> None:
    """Permanently delete the file, extracted text, embedding and cached scores.

    Applications made with it stay (the recruiter's record of the application), but no
    longer link to any resume data.
    """
    key = resume.storage_key
    db.execute(delete(Resume).where(Resume.id == resume.id))
    db.commit()
    _delete_files([key])


def delete_account(db: Session, user: User, password: str) -> int:
    """Seeker self-service erasure: account, profile, resumes, applications, notifications.

    Returns the number of files removed from storage.
    """
    if user.role != UserRole.seeker:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Recruiter and admin accounts are closed by an administrator",
        )
    if not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password is incorrect")
    keys = list(db.scalars(select(Resume.storage_key).where(Resume.user_id == user.id)))
    # Foreign keys cascade to every table holding this seeker's data.
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    _delete_files(keys)
    log.info("account deleted", extra={"user_id": user.id, "files": len(keys)})
    return len(keys)
