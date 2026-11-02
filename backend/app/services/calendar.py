"""Interview invites as iCalendar (RFC 5545) files and "Add to Google Calendar" links.

An .ics file works with Google Calendar, Outlook and Apple Calendar without any OAuth app:
it is attached to the invitation email and downloadable from the app. Reschedules keep the
same UID with a higher SEQUENCE, and a cancellation is sent as STATUS:CANCELLED, so calendar
clients update the existing event instead of adding a new one.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from app.core.config import settings
from app.models import Interview

MODE_LABELS = {"video": "Video call", "phone": "Phone call", "onsite": "On-site"}


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """Lines longer than 75 octets are folded with CRLF + space (RFC 5545 3.1)."""
    out, current = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(current) + len(b) > 75:
            out.append(current.decode("utf-8"))
            current = b" " + b
        else:
            current += b
    out.append(current.decode("utf-8"))
    return "\r\n".join(out)


def _utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def interview_title(iv: Interview) -> str:
    job = iv.application.job
    return f"Interview: {job.title} at {job.company.name}"


def interview_description(iv: Interview) -> str:
    app = iv.application
    lines = [
        f"{MODE_LABELS[iv.mode]} interview for {app.job.title} at {app.job.company.name}.",
        f"Candidate: {app.seeker.full_name}",
    ]
    if iv.location:
        lines.append(f"Where: {iv.location}")
    if iv.notes:
        lines.append(f"Notes: {iv.notes}")
    lines.append(f"Details: {settings.public_app_url}/applications")
    return "\n".join(lines)


def build_ics(iv: Interview, now: datetime | None = None) -> bytes:
    cancelled = iv.status == "cancelled"
    end = iv.starts_at + timedelta(minutes=iv.duration_minutes)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Hike//Interviews//EN",
        "CALSCALE:GREGORIAN",
        f"METHOD:{'CANCEL' if cancelled else 'REQUEST'}",
        "BEGIN:VEVENT",
        f"UID:interview-{iv.id}@hike",
        f"SEQUENCE:{iv.sequence}",
        f"DTSTAMP:{_utc(now or datetime.now(UTC))}",
        f"DTSTART:{_utc(iv.starts_at)}",
        f"DTEND:{_utc(end)}",
        f"SUMMARY:{_escape(interview_title(iv))}",
        f"DESCRIPTION:{_escape(interview_description(iv))}",
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
    ]
    if iv.location:
        lines.append(f"LOCATION:{_escape(iv.location)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")


def google_calendar_url(iv: Interview) -> str:
    end = iv.starts_at + timedelta(minutes=iv.duration_minutes)
    query = {
        "action": "TEMPLATE",
        "text": interview_title(iv),
        "dates": f"{_utc(iv.starts_at)}/{_utc(end)}",
        "details": interview_description(iv),
    }
    if iv.location:
        query["location"] = iv.location
    return "https://calendar.google.com/calendar/render?" + urlencode(query)
