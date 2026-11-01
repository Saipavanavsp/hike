from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MatchScore(Base):
    """Cached (resume, job) match. Stale when either signature no longer matches."""

    __tablename__ = "match_scores"

    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    score: Mapped[int] = mapped_column(SmallInteger)
    semantic: Mapped[float] = mapped_column(Float)
    skill_ratio: Mapped[float] = mapped_column(Float)
    experience_fit: Mapped[float] = mapped_column(Float)
    location_fit: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSONB)
    resume_hash: Mapped[str] = mapped_column(String(40))
    job_hash: Mapped[str] = mapped_column(String(40))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("ix_match_scores_job_score", "job_id", text("score DESC")),)


class EvalRun(Base):
    """Output of `python -m app.ml.eval`; /api/stats/public reads the latest row."""

    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    git_sha: Mapped[str | None] = mapped_column(String(40))
    metrics: Mapped[dict] = mapped_column(JSONB)
