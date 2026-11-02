"""Resume <-> job match score (0-100) with a human-readable breakdown.

    score = 100 * (0.50 * semantic + 0.35 * skill_overlap + 0.10 * experience_fit + 0.05 * location_fit)

- semantic: cosine similarity of all-MiniLM-L6-v2 embeddings (resume text vs job text),
  linearly rescaled from [SEM_FLOOR, SEM_CEIL] to [0, 1]. Raw MiniLM cosines between whole
  documents sit in a narrow band (~0.1-0.7), so without rescaling a perfect candidate
  would still score ~35/50 on this component. The constants are documented in the README.
- skill_overlap: required job skills found in the resume's confirmed skills / required skills.
- experience_fit: 1 inside [min, max]; -0.5 per missing year below; -0.1 per extra year above
  (floored at 0.6, being overqualified is a soft mismatch).
- location_fit: 1 if remote and the seeker is open to remote, or the job city is one of the
  seeker's cities (or the seeker set no location); else 0.

Results are cached in match_scores keyed by (resume, job) and invalidated through
content signatures, so a score is recomputed only when the resume, profile or job changes.
"""

import hashlib
import json
import re
from dataclasses import dataclass

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, undefer

from app.ml.classifier import get_classifier
from app.ml.embeddings import content_hash, embed_documents
from app.ml.skills import get_taxonomy
from app.models import Job, MatchScore, Resume, SeekerProfile
from app.models.enums import RemoteType, RoleCategory

W_SEMANTIC = 0.50
W_SKILLS = 0.35
W_EXPERIENCE = 0.10
W_LOCATION = 0.05
SEM_FLOOR = 0.15
SEM_CEIL = 0.65
# Bump when the breakdown format changes, so cached match_scores rows are recomputed.
BREAKDOWN_VERSION = 2
COMPONENT_LABELS = {
    "semantic": "Resume and job description similarity",
    "skills": "Required skills",
    "experience": "Experience",
    "location": "Location",
}


# ---------- pure scoring ----------


@dataclass
class ResumeSide:
    vector: np.ndarray
    skills: list[str]
    years: float | None
    locations: set[str]
    open_to_remote: bool


@dataclass
class JobSide:
    vector: np.ndarray
    skills: list[str]
    experience_min: int
    experience_max: int
    location: str
    remote_type: str


def semantic_component(cosine: float) -> float:
    return float(np.clip((cosine - SEM_FLOOR) / (SEM_CEIL - SEM_FLOOR), 0.0, 1.0))


def skill_overlap(resume_skills: list[str], job_skills: list[str]) -> tuple[list[str], list[str]]:
    tax = get_taxonomy()
    have = {(tax.canonical(s) or s).lower() for s in resume_skills}
    matched, missing = [], []
    for s in job_skills:
        (matched if (tax.canonical(s) or s).lower() in have else missing).append(s)
    return matched, missing


def experience_fit(years: float | None, lo: int, hi: int) -> tuple[float, bool]:
    if years is None:
        return 0.5, False
    if lo <= years <= hi:
        return 1.0, True
    if years < lo:
        return max(0.0, 1.0 - 0.5 * (lo - years)), False
    return max(0.6, 1.0 - 0.1 * (years - hi)), False


def location_fit(r: ResumeSide, job: JobSide) -> tuple[float, bool]:
    if job.remote_type == RemoteType.remote.value:
        ok = r.open_to_remote
    elif not r.locations:
        ok = True  # no stated preference = no constraint
    else:
        ok = job.location.lower() in r.locations
    return (1.0 if ok else 0.0), ok


def compute_match(r: ResumeSide, job: JobSide) -> dict:
    cosine = float(np.dot(r.vector, job.vector))
    sem = semantic_component(cosine)
    matched, missing = skill_overlap(r.skills, job.skills)
    skills_ratio = len(matched) / len(job.skills) if job.skills else 1.0
    exp_fit, exp_ok = experience_fit(r.years, job.experience_min, job.experience_max)
    loc_fit, loc_ok = location_fit(r, job)
    parts = [
        ("semantic", W_SEMANTIC, sem),
        ("skills", W_SKILLS, skills_ratio),
        ("experience", W_EXPERIENCE, exp_fit),
        ("location", W_LOCATION, loc_fit),
    ]
    score = sum(100 * w * v for _, w, v in parts)
    if r.years is None:
        exp_detail = (
            f"Experience not stated; job asks {job.experience_min}-{job.experience_max} yrs"
        )
    else:
        exp_detail = f"{r.years:g} yrs; job asks {job.experience_min}-{job.experience_max} yrs"
    if job.remote_type == RemoteType.remote.value:
        loc_detail = "Remote job; " + (
            "open to remote" if r.open_to_remote else "not open to remote"
        )
    else:
        loc_detail = f"Job in {job.location}; " + (
            "matches the candidate's locations"
            if loc_ok
            else "not one of the candidate's locations"
        )
    details = {
        "semantic": f"Text similarity {cosine:.2f} (scaled from {SEM_FLOOR}-{SEM_CEIL})",
        "skills": f"{len(matched)} of {len(job.skills)} required skills",
        "experience": exp_detail,
        "location": loc_detail,
    }
    components = [
        {
            "key": key,
            "label": COMPONENT_LABELS[key],
            "weight": int(round(100 * w)),
            "points": round(100 * w * v, 1),
            "detail": details[key],
        }
        for key, w, v in parts
    ]
    return {
        "score": int(round(score)),
        "components": components,
        "skills_matched": matched,
        "skills_missing": missing,
        "skills_ratio": f"{len(matched)}/{len(job.skills)}",
        "experience_ok": exp_ok,
        "experience_years": r.years,
        "location_ok": loc_ok,
        "semantic": round(sem, 4),
        "cosine": round(cosine, 4),
        "skill_overlap": round(skills_ratio, 4),
        "experience_fit": round(exp_fit, 4),
        "location_fit": round(loc_fit, 4),
    }


# ---------- embeddings & derived data ----------

_MD_RE = re.compile(r"[#*_`>\[\]]+")


def job_text(title: str, skills: list[str], description_md: str) -> str:
    desc = _MD_RE.sub(" ", description_md or "")
    return f"{title}. Skills: {', '.join(skills)}.\n{desc}"


def job_embedding_text(job: Job) -> str:
    return job_text(job.title, job.skills, job.description_md)


def ensure_job_embeddings(db: Session, jobs: list[Job]) -> None:
    stale = [(j, job_embedding_text(j)) for j in jobs]
    stale = [(j, t) for j, t in stale if j.embedding_hash != content_hash(t) or j.embedding is None]
    if not stale:
        return
    vecs = embed_documents([t for _, t in stale])
    for (job, text), vec in zip(stale, vecs, strict=True):
        job.embedding = vec
        job.embedding_hash = content_hash(text)
    db.commit()


def resume_matching_text(resume: Resume, account_name: str | None = None) -> str:
    """Resume text with the candidate's name, contacts and institutions removed."""
    from app.services.redaction import redact_identity

    parsed_name = (resume.parsed or {}).get("name")
    return redact_identity(resume.raw_text or "", [account_name, parsed_name])


def ensure_resume_derived(db: Session, resume: Resume) -> None:
    """Embedding + predicted role category for a resume (skipped if text unchanged).

    Both see the redacted text, so a candidate's name or college cannot move the score."""
    from app.models import User

    user = db.get(User, resume.user_id)
    text = resume_matching_text(resume, user.full_name if user else None)
    h = content_hash(text)
    if resume.embedding_hash == h and resume.embedding is not None:
        return
    resume.embedding = embed_documents([text])[0]
    resume.embedding_hash = h
    label, prob = get_classifier().predict(text)
    resume.predicted_category = RoleCategory(label)
    resume.category_confidence = round(prob, 4)
    db.commit()


# ---------- cached lookups ----------


def _sig(*parts) -> str:
    payload = json.dumps([BREAKDOWN_VERSION, *parts], default=str, sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()


def resume_side(db: Session, resume: Resume) -> tuple[ResumeSide, str]:
    profile = db.get(SeekerProfile, resume.user_id)
    locations: set[str] = set()
    open_to_remote = True
    if profile:
        locations = {loc.lower() for loc in (profile.preferred_locations or [])}
        if profile.current_location:
            locations.add(profile.current_location.lower())
        open_to_remote = profile.open_to_remote
    years = float(resume.years_experience) if resume.years_experience is not None else None
    side = ResumeSide(
        vector=np.asarray(resume.embedding, dtype=np.float32),
        skills=list(resume.skills or []),
        years=years,
        locations=locations,
        open_to_remote=open_to_remote,
    )
    sig = _sig(resume.embedding_hash, sorted(side.skills), years, sorted(locations), open_to_remote)
    return side, sig


def job_side(job: Job) -> tuple[JobSide, str]:
    side = JobSide(
        vector=np.asarray(job.embedding, dtype=np.float32),
        skills=list(job.skills),
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        location=job.location,
        remote_type=job.remote_type.value,
    )
    sig = _sig(
        job.embedding_hash,
        side.skills,
        job.experience_min,
        job.experience_max,
        job.location,
        side.remote_type,
    )
    return side, sig


def get_match_results(db: Session, resume: Resume, job_ids: list[int]) -> dict[int, dict]:
    """Breakdown dicts for each job id, served from match_scores when still fresh."""
    if not job_ids:
        return {}
    resume = db.scalar(
        select(Resume)
        .options(undefer(Resume.embedding), undefer(Resume.raw_text))
        .where(Resume.id == resume.id)
    )
    ensure_resume_derived(db, resume)
    jobs = list(db.scalars(select(Job).options(undefer(Job.embedding)).where(Job.id.in_(job_ids))))
    ensure_job_embeddings(db, jobs)
    r_side, r_sig = resume_side(db, resume)
    cached = {
        m.job_id: m
        for m in db.scalars(
            select(MatchScore).where(
                MatchScore.resume_id == resume.id, MatchScore.job_id.in_(job_ids)
            )
        )
    }
    out: dict[int, dict] = {}
    upserts = []
    for job in jobs:
        j_side, j_sig = job_side(job)
        hit = cached.get(job.id)
        if hit and hit.resume_hash == r_sig and hit.job_hash == j_sig:
            out[job.id] = hit.breakdown
            continue
        b = compute_match(r_side, j_side)
        out[job.id] = b
        upserts.append(
            {
                "resume_id": resume.id,
                "job_id": job.id,
                "score": b["score"],
                "semantic": b["semantic"],
                "skill_ratio": b["skill_overlap"],
                "experience_fit": b["experience_fit"],
                "location_fit": b["location_fit"],
                "breakdown": b,
                "resume_hash": r_sig,
                "job_hash": j_sig,
            }
        )
    if upserts:
        stmt = insert(MatchScore).values(upserts)
        stmt = stmt.on_conflict_do_update(
            index_elements=["resume_id", "job_id"],
            set_={
                **{c: stmt.excluded[c] for c in upserts[0] if c not in ("resume_id", "job_id")},
                "computed_at": func.now(),
            },
        )
        db.execute(stmt)
        db.commit()
    return out


def match_one(db: Session, resume: Resume, job_id: int) -> dict | None:
    return get_match_results(db, resume, [job_id]).get(job_id)
