"""Audit log of sensitive actions.

    record(db, actor, "admin.users.deactivate", "user", None, {"ids": [3, 4]}, request)

Entries are added to the caller's session and committed with its transaction, so an action
and its audit entry succeed or fail together. The request id ties an entry to the log lines
of the same request.
"""

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.observability import request_id_var
from app.models import AuditLog, User


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host[:45]


def record(
    db: Session,
    actor: User | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_role=actor.role.value if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
        ip=client_ip(request),
        request_id=request_id_var.get(),
    )
    db.add(entry)
    return entry
