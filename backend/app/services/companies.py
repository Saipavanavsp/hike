import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "company"


def get_or_create_company(db: Session, name: str) -> Company:
    name = " ".join(name.split())
    company = db.scalar(select(Company).where(func.lower(Company.name) == name.lower()))
    if company:
        return company
    base = slugify(name)
    slug, n = base, 2
    while db.scalar(select(Company.id).where(Company.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    company = Company(name=name, slug=slug)
    db.add(company)
    db.flush()
    return company
