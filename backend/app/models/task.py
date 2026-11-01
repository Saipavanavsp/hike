from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

TASK_STATUSES = ("queued", "running", "retrying", "succeeded", "rejected", "failed")


class BackgroundTask(Base):
    """One row per background job, so its status can be shown to users and monitored.

    The id doubles as the Celery task id.
    """

    __tablename__ = "background_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # What the task works on, e.g. ("resume", 12); lets the UI find a resume's parse task.
    ref_type: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    args: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'retrying', 'succeeded', 'rejected', 'failed')",
            name="ck_background_tasks_status",
        ),
        Index("ix_background_tasks_status_created", "status", "created_at"),
        Index("ix_background_tasks_ref", "ref_type", "ref_id"),
    )
