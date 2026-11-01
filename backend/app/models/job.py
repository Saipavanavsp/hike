from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.db.session import Base
from app.models.company import Company
from app.models.enums import JobStatus, RemoteType, RoleCategory, pg_enum


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(160))
    role_category: Mapped[RoleCategory] = mapped_column(pg_enum(RoleCategory, "role_category"))
    location: Mapped[str] = mapped_column(String(80))
    remote_type: Mapped[RemoteType] = mapped_column(pg_enum(RemoteType, "remote_type"))
    experience_min: Mapped[int] = mapped_column(SmallInteger)
    experience_max: Mapped[int] = mapped_column(SmallInteger)
    # Annual CTC in INR
    salary_min: Mapped[int] = mapped_column(Integer)
    salary_max: Mapped[int] = mapped_column(Integer)
    skills: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    description_md: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), default=JobStatus.open, server_default="open"
    )
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Maintained by the jobs_search_vector_update() trigger (see migration 0003).
    search_vector: Mapped[str | None] = deferred(mapped_column(TSVECTOR))

    company: Mapped[Company] = relationship(lazy="joined")

    __table_args__ = (
        CheckConstraint("experience_min >= 0 AND experience_min <= experience_max", "ck_jobs_exp"),
        CheckConstraint("salary_min > 0 AND salary_min <= salary_max", "ck_jobs_salary"),
        Index("ix_jobs_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_jobs_skills", "skills", postgresql_using="gin"),
        Index("ix_jobs_status_posted_at", "status", text("posted_at DESC")),
        Index("ix_jobs_recruiter_id", "recruiter_id"),
        Index("ix_jobs_location_remote", "location", "remote_type"),
        Index("ix_jobs_salary_max", "salary_max"),
        Index("ix_jobs_role_category", "role_category"),
    )


class SavedJob(Base):
    __tablename__ = "saved_jobs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
