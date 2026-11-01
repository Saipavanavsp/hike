import io
import zipfile
from datetime import date
from pathlib import Path

import pytest

from app.services.resume_parser import (
    DOCX_MIME,
    PDF_MIME,
    InvalidResumeFile,
    detect_kind,
    extract_text,
    parse_resume,
    years_from_ranges,
)

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 1)


def load(name: str):
    data = (FIXTURES / name).read_bytes()
    kind = "pdf" if name.endswith(".pdf") else "docx"
    return parse_resume(extract_text(data, kind), today=TODAY)


def test_pdf_backend_resume():
    p = load("priya_sharma_backend.pdf")
    assert p.name == "Priya Sharma"
    assert p.email == "priya.sharma.dev@example.com"
    assert p.phone == "+919876543210"
    assert p.location == "Hyderabad"
    for s in ["Python", "Django", "FastAPI", "PostgreSQL", "Redis", "Docker", "AWS", "Celery"]:
        assert s in p.skills
    # Jan-Jun 2022 (6 months) + Jul 2022-Nov 2026 (53 months); the B.Tech years are ignored.
    assert p.years_experience == pytest.approx(4.9)
    assert p.education == ["B.Tech in Computer Science, JNTU Hyderabad, 2018 - 2022, CGPA 8.4"]


def test_docx_frontend_resume_uses_explicit_years_and_aliases():
    p = load("arjun_menon_frontend.docx")
    assert p.name == "Arjun Menon"
    assert p.phone == "9123456789"
    assert p.location == "Bengaluru"
    assert p.years_experience == 4.0
    for s in [
        "React",
        "TypeScript",
        "Next.js",
        "Redux",
        "Tailwind CSS",
        "JavaScript",
        "PostgreSQL",
    ]:
        assert s in p.skills
    assert "Bachelor of Engineering" in p.education[0]


def test_pdf_data_resume_ignores_english_words():
    p = load("kavya_iyer_data.pdf")
    assert p.years_experience == 2.0
    assert {"scikit-learn", "PyTorch", "Apache Spark", "NLP", "Pandas"} <= set(p.skills)
    assert "Go" not in p.skills and "Spring" not in p.skills
    assert len(p.education) == 2


def test_overlapping_ranges_are_merged():
    text = "Jan 2020 - Dec 2021 Company A\nJun 2021 - Dec 2022 Company B (part-time)"
    assert years_from_ranges(text, TODAY) == 3.0


def test_en_dash_em_dash_and_to_separators():
    assert years_from_ranges("Jan 2024 – Dec 2024", TODAY) == 1.0
    assert years_from_ranges("Jan 2024 — Dec 2024", TODAY) == 1.0
    assert years_from_ranges("January 2024 to December 2024", TODAY) == 1.0


def test_ranges_with_years_only_and_bad_ranges():
    assert years_from_ranges("2019 - 2020", TODAY) == 2.0
    assert years_from_ranges("2030 - 2031", TODAY) is None
    assert years_from_ranges("no dates here", TODAY) is None


def test_missing_fields_are_none():
    p = parse_resume("just some words about nothing in particular, nothing more", today=TODAY)
    assert p.email is None and p.phone is None and p.years_experience is None
    assert p.skills == [] and p.education == []


# ---------- validation ----------


def test_detect_kind_accepts_real_files():
    pdf = (FIXTURES / "priya_sharma_backend.pdf").read_bytes()
    docx = (FIXTURES / "arjun_menon_frontend.docx").read_bytes()
    assert detect_kind("cv.pdf", PDF_MIME, pdf) == "pdf"
    assert detect_kind("CV.DOCX", DOCX_MIME, docx) == "docx"
    assert detect_kind("cv.pdf", None, pdf) == "pdf"


@pytest.mark.parametrize(
    "filename,mime,data,msg",
    [
        ("cv.txt", "text/plain", b"hello", "Only PDF or DOCX"),
        ("cv", None, b"%PDF-1.4", "Only PDF or DOCX"),
        ("cv.pdf", "application/msword", b"%PDF-1.4", "does not match"),
        ("cv.pdf", PDF_MIME, b"MZ fake exe", "not a valid PDF"),
        ("cv.docx", DOCX_MIME, b"not a zip", "not a valid DOCX"),
    ],
)
def test_detect_kind_rejects_bad_files(filename, mime, data, msg):
    with pytest.raises(InvalidResumeFile, match=msg):
        detect_kind(filename, mime, data)


def test_zip_without_word_document_is_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(InvalidResumeFile, match="not a valid DOCX"):
        detect_kind("cv.docx", DOCX_MIME, buf.getvalue())


def test_unreadable_pdf_is_rejected():
    with pytest.raises(InvalidResumeFile):
        extract_text(b"%PDF-1.4 garbage", "pdf")
