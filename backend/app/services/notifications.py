"""In-app notifications, each also delivered by email in a background task.

Email goes through services/email.py (logged by default, SMTP when configured), unless the
user turned email off. Delivery runs in the worker with retries; notifications.emailed_at
records when it happened. Interview notifications carry an .ics calendar invite.
"""

from datetime import UTC, datetime

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import Notification, User

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
    from app.core.config import settings
    from app.models import Interview
    from app.services import email
    from app.services.calendar import build_ics

    # Idempotent delivery: the row stays locked while the email is sent, so a duplicate task
    # running at the same time skips it, and a later rerun sees emailed_at and skips it.
    # If the process dies after sending but before the commit, the retry sends again with
    # the same Message-ID, which lets mail servers and clients drop the duplicate.
    n = db.scalar(
        select(Notification)
        .where(Notification.id == notification_id)
        .with_for_update(skip_locked=True)
    )
    if n is None:
        exists = db.scalar(select(Notification.id).where(Notification.id == notification_id))
        return {"skipped": "being sent by another worker" if exists else "notification deleted"}
    if n.emailed_at is not None:
        db.rollback()
        return {"skipped": "already sent"}
    user = db.get(User, n.user_id)
    if not user.email_notifications:
        return {"skipped": "user opted out of email"}
    body = n.body or ""
    if n.link:
        body = f"{body}\n\nOpen in Hike: {settings.public_app_url}{n.link}".strip()
    body += "\n\nYou can turn off these emails in your Hike profile."
    attachments = []
    interview_id = (n.payload or {}).get("interview_id")
    if interview_id:
        iv = db.get(Interview, interview_id)
        if iv is not None:
            attachments.append(
                email.Attachment(
                    "interview.ics",
                    build_ics(iv),
                    "text/calendar; method="
                    + ("CANCEL" if iv.status == "cancelled" else "REQUEST"),
                )
            )
    backend = email.send(
        email.OutgoingEmail(
            user.email, n.title, body, attachments, message_id=f"<notification-{n.id}@hike>"
        )
    )
    n.emailed_at = datetime.now(UTC)
    db.commit()
    return {"sent_to": user.id, "backend": backend, "attachments": len(attachments)}
