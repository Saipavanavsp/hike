from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.user import User


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True)
    logo_url: Mapped[str | None] = mapped_column(String(300))
    website: Mapped[str | None] = mapped_column(String(300))
    industry: Mapped[str | None] = mapped_column(String(80))
    size_range: Mapped[str | None] = mapped_column(String(40))
    hq_city: Mapped[str | None] = mapped_column(String(80))
    about: Mapped[str | None] = mapped_column(String(1000))


class RecruiterProfile(Base):
    __tablename__ = "recruiter_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str | None] = mapped_column(String(120))

    user: Mapped[User] = relationship(back_populates="recruiter_profile")
    company: Mapped[Company | None] = relationship()
