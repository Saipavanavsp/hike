"""Render resume data (dict) to PDF (reportlab) or DOCX (python-docx).

Used to generate the committed test fixtures and the seed resumes. Dev-only dependency.
"""

from pathlib import Path

import docx
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_name = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=16, leading=20)
_contact = ParagraphStyle("contact", fontName="Helvetica", fontSize=9, leading=12)
_h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=8)
_role = ParagraphStyle("role", fontName="Helvetica-Bold", fontSize=9.5, leading=12, spaceBefore=4)
_body = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=12.5)
_bullet = ParagraphStyle("bullet", parent=_body, leftIndent=10, bulletIndent=2)


def _contact_line(r: dict) -> str:
    parts = [r.get("location"), r.get("email"), r.get("phone"), r.get("links")]
    return " | ".join(p for p in parts if p)


def render_pdf(r: dict, path: Path) -> None:
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"{r['name']} - Resume",
        author=r["name"],
    )
    story = [Paragraph(r["name"], _name), Paragraph(_contact_line(r), _contact)]
    if r.get("summary"):
        story += [Paragraph("Summary", _h), Paragraph(r["summary"], _body)]
    if r.get("experience"):
        story.append(Paragraph("Experience", _h))
        for e in r["experience"]:
            story.append(Paragraph(f"{e['title']}, {e['company']} - {e['dates']}", _role))
            for b in e.get("bullets", []):
                story.append(Paragraph(b, _bullet, bulletText="-"))
    if r.get("projects"):
        story.append(Paragraph("Projects", _h))
        for p in r["projects"]:
            story.append(Paragraph(p, _bullet, bulletText="-"))
    if r.get("skills_text"):
        story += [Paragraph("Skills", _h), Paragraph(r["skills_text"], _body)]
    if r.get("education"):
        story.append(Paragraph("Education", _h))
        for ed in r["education"]:
            story.append(Paragraph(ed, _body))
    story.append(Spacer(1, 4))
    doc.build(story)


def render_docx(r: dict, path: Path) -> None:
    d = docx.Document()
    d.core_properties.author = r["name"]
    d.add_heading(r["name"], level=1)
    d.add_paragraph(_contact_line(r))
    if r.get("summary"):
        d.add_heading("Summary", level=2)
        d.add_paragraph(r["summary"])
    if r.get("experience"):
        d.add_heading("Experience", level=2)
        for e in r["experience"]:
            d.add_paragraph(f"{e['title']}, {e['company']} - {e['dates']}").runs[0].bold = True
            for b in e.get("bullets", []):
                d.add_paragraph(b, style="List Bullet")
    if r.get("projects"):
        d.add_heading("Projects", level=2)
        for p in r["projects"]:
            d.add_paragraph(p, style="List Bullet")
    if r.get("skills_text"):
        d.add_heading("Skills", level=2)
        d.add_paragraph(r["skills_text"])
    if r.get("education"):
        d.add_heading("Education", level=2)
        for ed in r["education"]:
            d.add_paragraph(ed)
    d.save(str(path))


_ = colors  # reportlab colour module kept available for future styling
