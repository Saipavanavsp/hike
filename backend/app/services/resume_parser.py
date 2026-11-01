"""Resume text extraction (PDF / DOCX) and rule-based field parsing."""

import io
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date

import docx
import pdfplumber

from app.ml.skills import get_taxonomy

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED = {".pdf": PDF_MIME, ".docx": DOCX_MIME}


class InvalidResumeFile(ValueError):
    pass


# ---------- file validation & text extraction ----------


def detect_kind(filename: str, content_type: str | None, data: bytes) -> str:
    """Validate extension, declared MIME type and the file's magic bytes. Returns 'pdf'|'docx'."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise InvalidResumeFile("Only PDF or DOCX files are accepted")
    if content_type and content_type != ALLOWED[ext]:
        raise InvalidResumeFile(f"File type {content_type} does not match {ext}")
    if ext == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise InvalidResumeFile("File is not a valid PDF")
        return "pdf"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "word/document.xml" not in z.namelist():
                raise InvalidResumeFile("File is not a valid DOCX document")
    except zipfile.BadZipFile as e:
        raise InvalidResumeFile("File is not a valid DOCX document") from e
    return "docx"


def extract_text(data: bytes, kind: str) -> str:
    try:
        if kind == "pdf":
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages[:10]]
            text = "\n".join(pages)
        else:
            d = docx.Document(io.BytesIO(data))
            parts = [p.text for p in d.paragraphs]
            for table in d.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            text = "\n".join(parts)
    except Exception as e:
        raise InvalidResumeFile("Could not read text from this file") from e
    text = text.replace("\x00", "").strip()
    if len(text) < 30:
        raise InvalidResumeFile(
            "No readable text found. Scanned resumes are not supported; export a text PDF."
        )
    return text


# ---------- field parsing ----------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?91[\s-]?)?(?<!\d)[6-9]\d{4}[\s-]?\d{5}(?!\d)")
EXPLICIT_YEARS_RE = re.compile(
    r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)\b(?:\s+of)?"
    r"(?:\s+(?:professional|industry|work|hands-on|total))?\s+experience",
    re.IGNORECASE,
)
MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
_MONTH = r"(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+)?"
RANGE_RE = re.compile(
    _MONTH
    + r"((?:19|20)\d{2})\s*(?:-|â€“|â€”|to)\s*"
    + _MONTH
    + r"((?:19|20)\d{2}|Present|Current|Now)",
    re.IGNORECASE,
)
# Case-sensitive on purpose: "BE" / "MS" as degrees, not the words "be" / "ms".
DEGREE_RE = re.compile(
    r"\b(?:B\.?\s?Tech|M\.?\s?Tech|B\.?\s?Sc|M\.?\s?Sc|BCA|MCA|MBA|B\.?\s?Com|Ph\.?\s?D|"
    r"(?i:bachelor(?:'s)?|master(?:'s)?|diploma))\b"
    r"|\bB\.\s?E\.?|\bBE\b|\bM\.S\.?|\bB\.S\.?"
)
SECTION_RE = re.compile(
    r"^\s*(work experience|professional experience|experience|employment history|employment|"
    r"education|academic background|skills|technical skills|projects|certifications|"
    r"achievements|summary|profile|objective|awards|publications|interests)\s*:?\s*$",
    re.IGNORECASE,
)
CITIES = {
    "bengaluru": "Bengaluru",
    "bangalore": "Bengaluru",
    "hyderabad": "Hyderabad",
    "chennai": "Chennai",
    "pune": "Pune",
    "mumbai": "Mumbai",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "noida": "Noida",
    "gurugram": "Gurugram",
    "gurgaon": "Gurugram",
    "kolkata": "Kolkata",
    "kochi": "Kochi",
    "ahmedabad": "Ahmedabad",
    "coimbatore": "Coimbatore",
    "jaipur": "Jaipur",
    "visakhapatnam": "Visakhapatnam",
    "vijayawada": "Vijayawada",
}


@dataclass
class ParsedResume:
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    years_experience: float | None = None
    skills: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def split_sections(text: str) -> dict[str, str]:
    """Map a normalised heading ("experience", "education", ...) to its body text."""
    sections: dict[str, list[str]] = {"_header": []}
    current = "_header"
    for line in text.splitlines():
        m = SECTION_RE.match(line)
        if m:
            heading = m.group(1).lower()
            if "experience" in heading or "employment" in heading:
                heading = "experience"
            elif "education" in heading or "academic" in heading:
                heading = "education"
            elif "skills" in heading:
                heading = "skills"
            current = heading
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v) for k, v in sections.items()}


def _month_index(month: str | None, year: int, default_month: int) -> int:
    m = MONTHS.get(month[:3].lower(), default_month) if month else default_month
    return year * 12 + (m - 1)


def years_from_ranges(text: str, today: date | None = None) -> float | None:
    """Total experience from date ranges, merging overlaps so parallel roles are not double counted."""
    today = today or date.today()
    now_idx = today.year * 12 + today.month - 1
    intervals = []
    for m1, y1, m2, y2 in RANGE_RE.findall(text):
        start = _month_index(m1, int(y1), 1)
        if y2.lower() in ("present", "current", "now"):
            end = now_idx
        else:
            end = _month_index(m2, int(y2), 12)
        if start <= end <= now_idx + 1:
            intervals.append((start, end))
    if not intervals:
        return None
    intervals.sort()
    total, (cur_s, cur_e) = 0, intervals[0]
    for s, e in intervals[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s + 1
            cur_s, cur_e = s, e
    total += cur_e - cur_s + 1
    return round(total / 12, 1)


def parse_years(text: str, sections: dict[str, str], today: date | None = None) -> float | None:
    explicit = [float(x) for x in EXPLICIT_YEARS_RE.findall(text)]
    if explicit:
        return max(explicit)
    exp_text = sections.get("experience")
    if exp_text:
        return years_from_ranges(exp_text, today)
    # No experience heading: use ranges from lines that are not about a degree.
    lines = [ln for ln in text.splitlines() if not DEGREE_RE.search(ln)]
    return years_from_ranges("\n".join(lines), today)


def parse_education(text: str, sections: dict[str, str]) -> list[str]:
    source = sections.get("education") or text
    out = []
    for line in source.splitlines():
        line = " ".join(line.split())
        if line and DEGREE_RE.search(line) and len(line) <= 160:
            out.append(line)
    return out[:3]


def parse_name(text: str) -> str | None:
    for line in text.splitlines()[:5]:
        line = line.strip()
        words = line.split()
        if (
            2 <= len(words) <= 4
            and not any(ch.isdigit() for ch in line)
            and "@" not in line
            and all(w.replace(".", "").replace("-", "").isalpha() for w in words)
        ):
            return line.title() if line.isupper() else line
    return None


def parse_location(text: str) -> str | None:
    head = " ".join(text.splitlines()[:6]).lower()
    for key, city in CITIES.items():
        if re.search(rf"\b{key}\b", head):
            return city
    return None


def parse_resume(text: str, today: date | None = None) -> ParsedResume:
    sections = split_sections(text)
    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    return ParsedResume(
        name=parse_name(text),
        email=email.group(0).lower() if email else None,
        phone=re.sub(r"[\s-]", "", phone.group(0)) if phone else None,
        location=parse_location(text),
        years_experience=parse_years(text, sections, today),
        skills=get_taxonomy().extract(text),
        education=parse_education(text, sections),
    )
