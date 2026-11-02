from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.core.signing import sign_resume_url, verify_resume_signature
from app.db.session import get_db
from app.ml.skills import get_taxonomy
from app.models import BackgroundTask, Resume, User
from app.models.enums import UserRole
from app.schemas.resumes import ResumeConfirm, ResumeOut, SignedLink, TaskOut
from app.services import audit
from app.services import resumes as resume_service
from app.services.file_scan import ScannerUnavailable
from app.services.resume_parser import InvalidResumeFile
from app.services.storage import get_storage

router = APIRouter(prefix="/api", tags=["resumes"])
seeker_only = require_role("seeker")


@router.post("/resumes", response_model=ResumeOut, status_code=status.HTTP_202_ACCEPTED)
def upload(
    file: UploadFile = File(...),
    consent: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(seeker_only),
):
    """Accepts the file and queues parsing. Poll GET /api/resumes/{id} until status is
    "ready" (then review and confirm) or "failed" (parse_error says why)."""
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)  # read one extra byte to detect oversize files
    try:
        return resume_service.upload_resume(
            db, user, file.filename or "resume", file.content_type, data, consent
        )
    except resume_service.ConsentRequired as e:
        raise HTTPException(422, str(e)) from e
    except InvalidResumeFile as e:
        raise HTTPException(413 if len(data) > limit else 422, str(e)) from e
    except ScannerUnavailable as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "File scanning is temporarily unavailable. Please try again in a few minutes.",
        ) from e


@router.get("/resumes", response_model=list[ResumeOut])
def list_resumes(db: Session = Depends(get_db), user: User = Depends(seeker_only)):
    return list(
        db.scalars(
            select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())
        )
    )


@router.get("/resumes/current", response_model=ResumeOut)
def get_current(db: Session = Depends(get_db), user: User = Depends(seeker_only)):
    resume = resume_service.current_resume(db, user.id)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No resume uploaded yet")
    return resume


@router.get("/resumes/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: int, db: Session = Depends(get_db), user: User = Depends(seeker_only)):
    return resume_service.get_own_resume(db, user, resume_id)


@router.put("/resumes/{resume_id}", response_model=ResumeOut)
def confirm(
    resume_id: int,
    data: ResumeConfirm,
    db: Session = Depends(get_db),
    user: User = Depends(seeker_only),
):
    resume = resume_service.get_own_resume(db, user, resume_id)
    return resume_service.confirm_resume(db, user, resume, data.skills, data.years_experience)


@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(seeker_only),
):
    """Permanently deletes the file and everything derived from it."""
    resume = resume_service.get_own_resume(db, user, resume_id)
    audit.record(db, user, "resume.delete", "resume", resume.id, None, request)
    resume_service.delete_resume(db, resume)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/resumes/{resume_id}/link", response_model=SignedLink)
def resume_link(
    resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """A short-lived URL for viewing the file, usable without the bearer token."""
    resume = db.get(Resume, resume_id)
    if resume is None or not resume_service.can_view_resume_file(db, user, resume):
        # 404 rather than 403 so resume ids cannot be probed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    url, expires = sign_resume_url(resume.id, user.id)
    return SignedLink(url=url, expires_at=expires)


@router.get("/files/resumes/{resume_id}", include_in_schema=False)
def signed_download(
    resume_id: int,
    uid: int,
    exp: int,
    request: Request,
    sig: str = Query(..., max_length=128),
    db: Session = Depends(get_db),
):
    if not verify_resume_signature(resume_id, uid, exp, sig):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This link is invalid or has expired")
    resume = db.get(Resume, resume_id)
    viewer = db.get(User, uid)
    if (
        resume is None
        or viewer is None
        or not resume_service.can_view_resume_file(db, viewer, resume)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    data = get_storage().read(resume.storage_key)
    if viewer.id != resume.user_id:
        # Who opened whose resume: personal data access by someone other than the owner.
        audit.record(
            db,
            viewer,
            "resume.file_access",
            "resume",
            resume.id,
            {"owner_id": resume.user_id},
            request,
        )
        db.commit()
    return Response(
        data,
        media_type=resume.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{resume.original_filename}"',
            "Cache-Control": "private, no-store",
            # Never sniffed as HTML; PDFs with scripts are already rejected at upload.
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get("/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
def task_status(
    task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    task = db.get(BackgroundTask, task_id)
    if task is None or (user.role != UserRole.admin and task.user_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    out = TaskOut.model_validate(task)
    if user.role != UserRole.admin:
        out.error = None  # may contain internals; user-facing reasons live on the resource
    return out


@router.get("/skills", response_model=list[str], tags=["skills"])
def search_skills(q: str = Query(..., min_length=1, max_length=40)):
    return get_taxonomy().search(q)
