"""Interviews, saved-search alerts and the audit log."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.application import Application

INTERVIEW_MODES = ("video", "phone", "onsite")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    scheduled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(10))
    location: Mapped[str | None] = mapped_column(String(300))  # meeting link or address
    notes: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(12), default="scheduled", server_default="scheduled")
    # Incremented on every reschedule/cancel, as iCalendar SEQUENCE requires.
    sequence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    application: Mapped[Application] = relationship(lazy="joined")

    __table_args__ = (
        CheckConstraint("mode IN ('video', 'phone', 'onsite')", name="ck_interviews_mode"),
        CheckConstraint("status IN ('scheduled', 'cancelled')", name="ck_interviews_status"),
        CheckConstraint("duration_minutes BETWEEN 15 AND 480", name="ck_interviews_duration"),
        Index("ix_interviews_application", "application_id"),
        Index("ix_interviews_starts_at", "starts_at"),
    )


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    # q, location[], role[], remote[], experience: the same fields as GET /api/jobs.
    params: Mapped[dict] = mapped_column(JSONB)
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_saved_searches_user", "user_id"),
        Index(
            "ix_saved_searches_alerts",
            "alerts_enabled",
            postgresql_where=text("alerts_enabled"),
        ),
    )


class AuditLog(Base):
    """Append-only record of sensitive actions (admin, recruiter and data access)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # NULL once the actor's account is deleted; actor_role keeps what kind of user it was.
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_role: Mapped[str | None] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str | None] = mapped_column(String(30))
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    ip: Mapped[str | None] = mapped_column(String(45))
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_audit_logs_created", text("created_at DESC")),
        Index("ix_audit_logs_actor", "actor_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_target", "target_type", "target_id"),
    )
