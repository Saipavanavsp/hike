import enum

from sqlalchemy import Enum


class UserRole(enum.StrEnum):
    seeker = "seeker"
    recruiter = "recruiter"
    admin = "admin"


class RemoteType(enum.StrEnum):
    onsite = "onsite"
    hybrid = "hybrid"
    remote = "remote"


class JobStatus(enum.StrEnum):
    open = "open"
    closed = "closed"


class RoleCategory(enum.StrEnum):
    backend = "backend"
    frontend = "frontend"
    fullstack = "fullstack"
    data_ml = "data_ml"
    devops = "devops"
    mobile = "mobile"
    qa = "qa"


class ApplicationStatus(enum.StrEnum):
    applied = "applied"
    shortlisted = "shortlisted"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Postgres enum that stores the member values (lowercase strings)."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
