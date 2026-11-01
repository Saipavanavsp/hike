"""Short-lived signed URLs for resume downloads.

A signed link names the resume, the viewer it was issued to and an expiry time, and carries
an HMAC-SHA256 over all three. It can be opened in a new tab without a bearer token, stops
working after SIGNED_URL_TTL_SECONDS, and is checked against the viewer's current access
when used (a deactivated recruiter's old links stop working).
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode

from app.core.config import settings


def _key() -> bytes:
    return hashlib.sha256(f"hike-url-signing:{settings.jwt_secret}".encode()).digest()


def _sig(resource: str, resource_id: int, viewer_id: int, expires: int) -> str:
    msg = f"{resource}:{resource_id}:{viewer_id}:{expires}".encode()
    return hmac.new(_key(), msg, hashlib.sha256).hexdigest()


def sign_resume_url(resume_id: int, viewer_id: int, now: float | None = None) -> tuple[str, int]:
    expires = int((now or time.time()) + settings.signed_url_ttl_seconds)
    query = urlencode(
        {"uid": viewer_id, "exp": expires, "sig": _sig("resume", resume_id, viewer_id, expires)}
    )
    return f"/api/files/resumes/{resume_id}?{query}", expires


def verify_resume_signature(
    resume_id: int, viewer_id: int, expires: int, sig: str, now: float | None = None
) -> bool:
    if expires < (now or time.time()):
        return False
    return hmac.compare_digest(sig, _sig("resume", resume_id, viewer_id, expires))
