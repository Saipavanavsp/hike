"""Load the demo dataset into the database.

    python -m seed.seed             # seed (fails if data exists)
    python -m seed.seed --if-empty  # seed only when there are no users (used on container start)
    python -m seed.seed --reset     # wipe all tables first (local development only)

Creates 1 admin, 3 recruiters, 20 seekers with parsed resumes, 20 fictional companies,
50 jobs and ~60 applications spread across every pipeline stage, then runs the evaluation
harness and stores its metrics so the landing page can show them.
"""

import argparse
import hashlib
import json
import logging
import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal
from app.models import (
    Application,
    ApplicationStatusHistory,
    Company,
    Job,
    Notification,
    RecruiterProfile,
    Resume,
    SeekerProfile,
    User,
)
from app.models.enums import ApplicationStatus, RemoteType, RoleCategory, UserRole
from app.services.cache import bump_jobs_version
from app.services.companies import slugify
from app.services.matching import ensure_job_embeddings, ensure_resume_derived, get_match_results
from app.services.resume_parser import PDF_MIME, extract_text, parse_resume
from app.services.storage import get_storage

log = logging.getLogger("seed")
HERE = Path(__file__).parent
DATA = HERE / "data"

ADMIN = ("Site Admin", "admin@example.com", "Admin@123")
RECRUITERS = [
    ("meera", "Meera Nair", 0),
    ("rohan", "Rohan Kapoor", 7),
    ("ananya", "Ananya Desai", 14),
]
RECRUITER_PASSWORD = "Recruiter@123"
SEEKER_PASSWORD = "Seeker@123"
APPLICATIONS_PER_SEEKER = 3

S = ApplicationStatus
# Final status -> path through the pipeline (after the initial "applied").
PATHS = {
    S.applied: [],
    S.shortlisted: [S.shortlisted],
    S.interview: [S.shortlisted, S.interview],
    S.offer: [S.shortlisted, S.interview, S.offer],
    S.rejected: [S.rejected],
}
STATUS_WEIGHTS = [
    (S.applied, 40),
    (S.shortlisted, 20),
    (S.interview, 15),
    (S.offer, 8),
    (S.rejected, 17),
]


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def reset(db: Session) -> None:
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    db.commit()


def make_user(db: Session, name: str, email: str, password: str, role: UserRole) -> User:
    u = User(email=email, full_name=name, password_hash=hash_password(password), role=role)
    db.add(u)
    db.flush()
    return u


def seed(db: Session, rng: random.Random, run_eval: bool = True) -> dict:
    now = datetime.now(UTC)
    companies_data = load("companies.json")
    jobs_data = load("jobs.json")
    resumes_data = load("resumes.json")

    # ---- companies & users ----
    companies: dict[str, Company] = {}
    for c in companies_data:
        company = Company(
            name=c["name"],
            slug=slugify(c["name"]),
            industry=c["industry"],
            size_range=c["size_range"],
            hq_city=c["hq_city"],
            about=c["about"],
        )
        db.add(company)
        companies[c["name"]] = company
    db.flush()

    make_user(db, ADMIN[0], ADMIN[1], ADMIN[2], UserRole.admin)
    recruiters: dict[str, User] = {}
    for key, name, company_idx in RECRUITERS:
        u = make_user(db, name, f"{key}@example.com", RECRUITER_PASSWORD, UserRole.recruiter)
        company = companies[companies_data[company_idx]["name"]]
        db.add(RecruiterProfile(user_id=u.id, company_id=company.id, title="Talent Partner"))
        recruiters[key] = u
    db.flush()

    # ---- jobs ----
    jobs: list[Job] = []
    for j in jobs_data:
        job = Job(
            recruiter_id=recruiters[j["recruiter"]].id,
            company_id=companies[j["company"]].id,
            title=j["title"],
            role_category=RoleCategory(j["role_category"]),
            location=j["location"],
            remote_type=RemoteType(j["remote_type"]),
            experience_min=j["experience_min"],
            experience_max=j["experience_max"],
            salary_min=j["salary_min"],
            salary_max=j["salary_max"],
            skills=j["skills"],
            description_md=j["description_md"],
            posted_at=now - timedelta(days=j["posted_days_ago"]),
        )
        db.add(job)
        jobs.append(job)
    db.commit()
    log.info("embedding %d jobs", len(jobs))
    ensure_job_embeddings(db, jobs)

    # ---- seekers & resumes (parsed from the PDFs with the real parser) ----
    storage = get_storage()
    seekers: list[tuple[User, Resume]] = []
    for r in resumes_data:
        user = make_user(db, r["name"], r["email"], SEEKER_PASSWORD, UserRole.seeker)
        pdf = (HERE / "resumes" / r["file"]).read_bytes()
        text_ = extract_text(pdf, "pdf")
        parsed = parse_resume(text_)
        key = f"resumes/{user.id}/seed-{r['file']}"
        storage.save(key, pdf, PDF_MIME)
        years = parsed.years_experience
        resume = Resume(
            user_id=user.id,
            storage_key=key,
            original_filename=r["file"],
            mime_type=PDF_MIME,
            size_bytes=len(pdf),
            raw_text=text_,
            status="ready",
            consent_at=now - timedelta(days=30),
            consent_version=settings.consent_version,
            file_sha256=hashlib.sha256(pdf).hexdigest(),
            scan_result="seed:trusted",
            parsed=parsed.to_dict(),
            skills=parsed.skills,
            years_experience=Decimal(str(years)) if years is not None else None,
            is_current=True,
            confirmed_at=now - timedelta(days=30),
            created_at=now - timedelta(days=30),
        )
        db.add(resume)
        db.add(
            SeekerProfile(
                user_id=user.id,
                headline=r["title"],
                current_location=parsed.location or r["location"],
                preferred_locations=[r["location"]],
                open_to_remote=True,
                years_experience=resume.years_experience,
                phone=parsed.phone,
            )
        )
        db.flush()
        seekers.append((user, resume))
    db.commit()
    log.info("embedding and classifying %d resumes", len(seekers))
    for _, resume in seekers:
        ensure_resume_derived(db, resume)

    # ---- applications: each seeker applies to their best-matching open jobs ----
    job_ids = [j.id for j in jobs]
    by_id = {j.id: j for j in jobs}
    statuses, weights = zip(*STATUS_WEIGHTS, strict=True)
    n_apps = 0
    for user, resume in seekers:
        scores = get_match_results(db, resume, job_ids)
        ranked = sorted(job_ids, key=lambda jid: -scores[jid]["score"])
        for jid in ranked[:APPLICATIONS_PER_SEEKER]:
            job = by_id[jid]
            final = rng.choices(statuses, weights)[0]
            age_days = (now - job.posted_at).total_seconds() / 86400
            # Most applications land within ~2 weeks so the weekly chart has data.
            applied_at = now - timedelta(days=rng.uniform(0, min(age_days, 14)))
            app = Application(
                job_id=jid,
                seeker_id=user.id,
                resume_id=resume.id,
                status=final,
                applied_at=applied_at,
                note=rng.choice(
                    [None, None, "Available to join in 30 days.", "Notice period: 60 days."]
                ),
            )
            db.add(app)
            db.flush()
            db.add(
                ApplicationStatusHistory(
                    application_id=app.id,
                    from_status=None,
                    to_status=S.applied,
                    changed_by=user.id,
                    changed_at=applied_at,
                )
            )
            t, prev = applied_at, S.applied
            steps = PATHS[final]
            # Keep every step strictly between the application time and now.
            max_gap = (now - applied_at) / (len(steps) + 1)
            for step in steps:
                t = t + min(timedelta(hours=rng.uniform(6, 60)), max_gap)
                db.add(
                    ApplicationStatusHistory(
                        application_id=app.id,
                        from_status=prev,
                        to_status=step,
                        changed_by=job.recruiter_id,
                        changed_at=t,
                    )
                )
                prev = step
            app.updated_at = t
            db.add(
                Notification(
                    user_id=job.recruiter_id,
                    type="application_received",
                    title=f"New application: {user.full_name} for {job.title}",
                    link=f"/recruiter/jobs/{job.id}",
                    created_at=applied_at,
                    read_at=applied_at + timedelta(hours=2) if final != S.applied else None,
                )
            )
            n_apps += 1
    db.commit()
    bump_jobs_version()

    metrics = None
    if run_eval:
        from app.ml import eval as ev

        log.info("running evaluation harness")
        metrics = ev.run()
        ev.RESULTS_PATH.write_text(json.dumps(metrics, indent=1), encoding="utf-8")
        ev.save_to_db(metrics)

    return {
        "companies": len(companies),
        "jobs": len(jobs),
        "seekers": len(seekers),
        "recruiters": len(recruiters),
        "applications": n_apps,
        "precision_at_5": (
            metrics["matching"]["methods"]["hike"]["precision_at_5"] if metrics else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Seed the Hike demo dataset")
    ap.add_argument("--if-empty", action="store_true", help="skip when users already exist")
    ap.add_argument("--reset", action="store_true", help="truncate all tables first")
    ap.add_argument("--no-eval", action="store_true", help="skip the evaluation run")
    args = ap.parse_args(argv)

    with SessionLocal() as db:
        has_users = db.scalar(select(func.count()).select_from(User)) > 0
        if args.reset:
            reset(db)
        elif has_users:
            if args.if_empty:
                log.info("database already has data; skipping seed")
                return 0
            log.error("database is not empty; use --reset to wipe it")
            return 1
        summary = seed(db, random.Random(7), run_eval=not args.no_eval)
    log.info("seeded: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
