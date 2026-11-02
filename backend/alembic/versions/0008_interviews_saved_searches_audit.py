"""interviews, saved-search alerts, audit log, email preference

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-02 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=nullable
    )


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_notifications", sa.Boolean(), server_default="true", nullable=False),
    )

    op.create_table(
        "interviews",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=False),
        sa.Column("scheduled_by", sa.BigInteger(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=12), server_default="scheduled", nullable=False),
        sa.Column("sequence", sa.Integer(), server_default="0", nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint("mode IN ('video', 'phone', 'onsite')", name="ck_interviews_mode"),
        sa.CheckConstraint("status IN ('scheduled', 'cancelled')", name="ck_interviews_status"),
        sa.CheckConstraint("duration_minutes BETWEEN 15 AND 480", name="ck_interviews_duration"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scheduled_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interviews_application", "interviews", ["application_id"])
    op.create_index("ix_interviews_starts_at", "interviews", ["starts_at"])

    op.create_table(
        "saved_searches",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("alerts_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_alert_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_searches_user", "saved_searches", ["user_id"])
    op.create_index(
        "ix_saved_searches_alerts",
        "saved_searches",
        ["alerts_enabled"],
        postgresql_where=sa.text("alerts_enabled"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=True),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        _ts("created_at"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_created", "audit_logs", [sa.literal_column("created_at DESC")])
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("saved_searches")
    op.drop_table("interviews")
    op.drop_column("users", "email_notifications")
