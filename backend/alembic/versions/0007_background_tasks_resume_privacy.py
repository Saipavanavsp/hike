"""background tasks, resume processing status, consent, privacy

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-01 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_tasks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("ref_type", sa.String(length=30), nullable=True),
        sa.Column("ref_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "args", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'retrying', 'succeeded', 'rejected', 'failed')",
            name="ck_background_tasks_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_background_tasks_status_created", "background_tasks", ["status", "created_at"]
    )
    op.create_index("ix_background_tasks_ref", "background_tasks", ["ref_type", "ref_id"])

    # Existing resumes were parsed synchronously, so they are "ready".
    op.add_column(
        "resumes", sa.Column("status", sa.String(length=20), server_default="ready", nullable=False)
    )
    op.create_check_constraint(
        "ck_resumes_status", "resumes", "status IN ('processing', 'ready', 'failed')"
    )
    op.add_column("resumes", sa.Column("parse_error", sa.String(length=300), nullable=True))
    op.add_column("resumes", sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("resumes", sa.Column("consent_version", sa.String(length=20), nullable=True))
    op.add_column("resumes", sa.Column("file_sha256", sa.String(length=64), nullable=True))
    op.add_column("resumes", sa.Column("scan_result", sa.String(length=60), nullable=True))
    op.alter_column("resumes", "raw_text", existing_type=sa.Text(), nullable=True)
    op.create_index("ix_resumes_status_created", "resumes", ["status", "created_at"])

    # A deleted resume must not delete the application record the recruiter relies on.
    op.alter_column("applications", "resume_id", existing_type=sa.BigInteger(), nullable=True)
    op.drop_constraint("applications_resume_id_fkey", "applications", type_="foreignkey")
    op.create_foreign_key(
        "applications_resume_id_fkey",
        "applications",
        "resumes",
        ["resume_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "notifications", sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("notifications", "emailed_at")
    op.drop_constraint("applications_resume_id_fkey", "applications", type_="foreignkey")
    op.create_foreign_key(
        "applications_resume_id_fkey", "applications", "resumes", ["resume_id"], ["id"]
    )
    op.alter_column("applications", "resume_id", existing_type=sa.BigInteger(), nullable=False)
    op.drop_index("ix_resumes_status_created", table_name="resumes")
    op.alter_column("resumes", "raw_text", existing_type=sa.Text(), nullable=False)
    for col in ("scan_result", "file_sha256", "consent_version", "consent_at", "parse_error"):
        op.drop_column("resumes", col)
    op.drop_constraint("ck_resumes_status", "resumes", type_="check")
    op.drop_column("resumes", "status")
    op.drop_index("ix_background_tasks_ref", table_name="background_tasks")
    op.drop_index("ix_background_tasks_status_created", table_name="background_tasks")
    op.drop_table("background_tasks")
