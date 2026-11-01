"""In-app notifications. Emails are not sent; they are written to the log instead."""

import logging

from sqlalchemy.orm import Session

from app.models import Notification, User

log = logging.getLogger("hike.email")


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
    log.info("[email] to=%s subject=%r body=%r", user.email, title, body)
    return n
