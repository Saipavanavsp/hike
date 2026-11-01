from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.ml.skills import get_taxonomy
from app.models import Resume, User
from app.schemas.resumes import ResumeConfirm, ResumeOut
from app.services import resumes as resume_service
from app.services.resume_parser import InvalidResumeFile
from app.services.storage import get_storage

router = APIRouter(prefix="/api", tags=["resumes"])
seeker_only = require_role("seeker")


@router.post("/resumes", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
def upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(seeker_only),
):
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)  # read one extra byte to detect oversize files
    try:
        return resume_service.upload_resume(
            db, user, file.filename or "resume", file.content_type, data
        )
    except InvalidResumeFile as e:
        raise HTTPException(413 if len(data) > limit else 422, str(e)) from e


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


@router.get("/resumes/{resume_id}/file")
def download(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = db.get(Resume, resume_id)
    if resume is None or not resume_service.can_view_resume_file(db, user, resume):
        # 404 rather than 403 so resume ids cannot be probed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    data = get_storage().read(resume.storage_key)
    return Response(
        data,
        media_type=resume.mime_type,
        headers={"Content-Disposition": f'inline; filename="{resume.original_filename}"'},
    )


@router.get("/skills", response_model=list[str], tags=["skills"])
def search_skills(q: str = Query(..., min_length=1, max_length=40)):
    return get_taxonomy().search(q)
