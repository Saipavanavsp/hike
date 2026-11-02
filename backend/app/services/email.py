"""Outgoing email. EMAIL_BACKEND=log (default) writes each message to the "hike.email"
logger; EMAIL_BACKEND=smtp sends it through any SMTP server (Brevo, Resend, SES, Gmail...)."""

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger("hike.email")


@dataclass
class Attachment:
    filename: str
    content: bytes
    mime: str  # e.g. "text/calendar; method=REQUEST"


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    body: str
    attachments: list[Attachment] = field(default_factory=list)
    # Stable per notification, so a re-sent duplicate is recognisable as the same message.
    message_id: str | None = None


def build_message(mail: OutgoingEmail) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = mail.to
    msg["Subject"] = mail.subject
    if mail.message_id:
        msg["Message-ID"] = mail.message_id
    msg.set_content(mail.body)
    for a in mail.attachments:
        maintype, _, rest = a.mime.partition("/")
        subtype, _, params = rest.partition(";")
        msg.add_attachment(
            a.content,
            maintype=maintype,
            subtype=subtype.strip(),
            filename=a.filename,
            params=dict(p.strip().split("=", 1) for p in params.split(";") if "=" in p),
        )
    return msg


def send(mail: OutgoingEmail) -> str:
    """Deliver one email; returns the backend used. SMTP errors propagate (the task retries)."""
    if settings.email_backend == "smtp":
        msg = build_message(mail)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return "smtp"
    log.info(
        "[email] to=%s subject=%r body=%r",
        mail.to,
        mail.subject,
        mail.body,
        extra={
            "attachments": [a.filename for a in mail.attachments],
            "message_id": mail.message_id,
        },
    )
    return "log"
