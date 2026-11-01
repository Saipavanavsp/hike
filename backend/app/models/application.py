from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ApplicationStatus, pg_enum
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    seeker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # The resume version the seeker applied with.
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"))
    note: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ApplicationStatus] = mapped_column(
        pg_enum(ApplicationStatus, "application_status"),
        default=ApplicationStatus.applied,
        server_default="applied",
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped[Job] = relationship(lazy="joined")
    seeker: Mapped[User] = relationship(lazy="joined")
    resume: Mapped[Resume] = relationship()
    history: Mapped[list["ApplicationStatusHistory"]] = relationship(
        order_by="ApplicationStatusHistory.changed_at", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # One application per seeker per job, enforced by the database.
        UniqueConstraint("job_id", "seeker_id", name="uq_applications_job_seeker"),
        Index("ix_applications_seeker_applied", "seeker_id", text("applied_at DESC")),
        Index("ix_applications_job_status", "job_id", "status"),
    )


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        pg_enum(ApplicationStatus, "application_status")
    )
    to_status: Mapped[ApplicationStatus] = mapped_column(
        pg_enum(ApplicationStatus, "application_status")
    )
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actor: Mapped[User | None] = relationship(lazy="joined")

    __table_args__ = (Index("ix_status_history_app_changed", "application_id", "changed_at"),)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(String(1000))
    link: Mapped[str | None] = mapped_column(String(300))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", text("created_at DESC")),
        Index("ix_notifications_unread", "user_id", postgresql_where=text("read_at IS NULL")),
    )
