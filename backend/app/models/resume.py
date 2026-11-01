from datetime import datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.db.session import Base
from app.models.enums import RoleCategory, pg_enum


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    storage_key: Mapped[str] = mapped_column(String(300))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = deferred(mapped_column(Text))
    # Raw parser output: name, email, phone, location, education, years, skills.
    parsed: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Seeker-confirmed values (editable after parsing).
    skills: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    years_experience: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    embedding: Mapped[Any | None] = deferred(mapped_column(Vector(384)))
    embedding_hash: Mapped[str | None] = mapped_column(String(40))
    predicted_category: Mapped[RoleCategory | None] = mapped_column(
        pg_enum(RoleCategory, "role_category")
    )
    category_confidence: Mapped[float | None] = mapped_column(Float)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_resumes_user_id", "user_id"),
        Index("ix_resumes_skills", "skills", postgresql_using="gin"),
        # At most one current resume per seeker.
        Index(
            "uq_resumes_one_current",
            "user_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )
