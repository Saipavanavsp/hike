"""Remove identity details from resume text before it reaches the embedding model.

The holdout fairness check showed that swapping only a candidate's name (to names linked
with a different gender, region or religion) moved MiniLM similarity enough to change match
scores by up to 9 points. Names, contact details and institution names say nothing about
job fit, so the semantic component and the role classifier see a redacted text. Skills,
experience and location are still parsed from the full text, and recruiters still see the
original resume.
"""

import re

from app.services.resume_parser import EMAIL_RE, PHONE_RE

_INSTITUTION = re.compile(
    r"(?:\b[A-Z][\w.&'-]*\s+){0,6}"
    r"(?:Institute|College|University|Polytechnic|Academy|School|Vidyalaya|Vidyapeeth)\b"
    r"(?:\s+(?:of|for)(?:\s+(?:and\s+)?[A-Z][\w&'-]*){1,5})?"
)
_URL = re.compile(r"\b(?:https?://|www\.)\S+|\b(?:linkedin|github)\.com/\S+", re.IGNORECASE)


def redact_identity(text: str, names: list[str | None]) -> str:
    # Contacts first: an email such as "priya.s@..." contains the name, and removing the
    # name first would leave a fragment the email pattern no longer matches.
    text = EMAIL_RE.sub(" ", text)
    text = PHONE_RE.sub(" ", text)
    text = _URL.sub(" ", text)
    for name in names:
        for token in (name or "").split():
            if len(token) >= 2:
                text = re.sub(rf"\b{re.escape(token)}\b", " ", text, flags=re.IGNORECASE)
    text = _INSTITUTION.sub("[institution]", text)
    return re.sub(r"[ \t]+", " ", text)
