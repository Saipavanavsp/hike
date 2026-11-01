"""In-app notifications, each also delivered by email in a background task.

Emails go to the log (logger "hike.email"): no mail provider is configured. Delivery runs
in the worker with retries, and notifications.emailed_at records when it happened.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import Notification, User

log = logging.getLogger("hike.email")
_PENDING = "pending_email_ids"


def notify(
    db: Session,
    user: User,
    type_: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    payload: dict | None = None,
) -> Notification:
    n = Notification(
        user_id=user.id, type=type_, title=title, body=body, link=link, payload=payload or {}
    )
    db.add(n)
    db.flush()
    # Queued only once the notification is committed, so the worker can see the row.
    db.info.setdefault(_PENDING, []).append(n.id)
    return n


@event.listens_for(Session, "after_commit")
def _queue_pending_emails(session: Session) -> None:
    ids = session.info.pop(_PENDING, None)
    if not ids:
        return
    from app.tasks.definitions import deliver_email
    from app.tasks.tracking import enqueue

    for nid in ids:
        enqueue(deliver_email, nid, ref_id=nid)


@event.listens_for(Session, "after_rollback")
def _drop_pending_emails(session: Session) -> None:
    session.info.pop(_PENDING, None)


def send_email(db: Session, notification_id: int) -> dict:
    n = db.get(Notification, notification_id)
    if n is None:
        return {"skipped": "notification deleted"}
    if n.emailed_at is not None:
        return {"skipped": "already sent"}
    user = db.get(User, n.user_id)
    log.info(
        "[email] to=%s subject=%r body=%r",
        user.email,
        n.title,
        n.body,
        extra={"notification_id": n.id, "email_type": n.type},
    )
    n.emailed_at = datetime.now(UTC)
    db.commit()
    return {"sent_to": user.id}
