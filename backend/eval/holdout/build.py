"""Render the holdout resumes into documents, in four layouts, with the real parser in mind.

    python -m eval.holdout.build        (from backend/; dev dependencies: reportlab)

Writes eval/holdout/files/<key>.<pdf|docx> in each resume's own layout, and
eval/holdout/variants/<key>-<layout>.<ext> for the format-invariance subset (the same
content in every layout). Layouts differ the way real resumes do:

  pdf_classic     one column, headings, "Mon YYYY - Mon YYYY"
  pdf_two_column  skills/education in a left sidebar, experience on the right,
                  en-dash date ranges; text extraction interleaves the columns
  docx_table      everything inside a two-column Word table, "|" separated skills
  docx_caps       ALL-CAPS headings without Word heading styles, "•" bullets,
                  "Mon YYYY to Present"
"""

import json
from pathlib import Path

import docx
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, PageTemplate, Paragraph

from seed.render import render_pdf

HERE = Path(__file__).parent
FILES = HERE / "files"
VARIANTS = HERE / "variants"
INVARIANCE_SUBSET = ["r01", "r05", "r10", "r14", "r17", "r22"]
EXT = {"pdf_classic": "pdf", "pdf_two_column": "pdf", "docx_table": "docx", "docx_caps": "docx"}

_name = ParagraphStyle("n", fontName="Helvetica-Bold", fontSize=15, leading=19)
_small = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5, leading=11)
_h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10, leading=13, spaceBefore=7)
_body = ParagraphStyle("b", fontName="Helvetica", fontSize=9, leading=12)
_role = ParagraphStyle("r", fontName="Helvetica-Bold", fontSize=9, leading=12, spaceBefore=4)


def _dates(e: dict, sep: str) -> str:
    return e["dates"].replace(" - ", sep)


def render_two_column(r: dict, path: Path) -> None:
    doc = BaseDocTemplate(str(path), pagesize=A4, title=r["name"], author=r["name"])
    w, h = A4
    margin = 14 * mm
    left_w = 58 * mm
    left = Frame(margin, margin, left_w, h - 2 * margin, id="left", showBoundary=0)
    right = Frame(
        margin + left_w + 6 * mm,
        margin,
        w - 2 * margin - left_w - 6 * mm,
        h - 2 * margin,
        id="right",
    )
    doc.addPageTemplates([PageTemplate(id="two", frames=[left, right])])
    side = [
        Paragraph(r["name"], _name),
        Paragraph(r["location"], _small),
        Paragraph(r["email"], _small),
        Paragraph(r["phone"], _small),
        Paragraph("Skills", _h),
        Paragraph(r["skills_text"], _small),
        Paragraph("Education", _h),
        *[Paragraph(ed, _small) for ed in r["education"]],
    ]
    main = [Paragraph("Profile", _h), Paragraph(r["summary"], _body), Paragraph("Experience", _h)]
    for e in r["experience"]:
        main.append(Paragraph(f"{e['title']} | {e['company']}", _role))
        main.append(Paragraph(_dates(e, " – "), _small))
        main += [Paragraph(f"- {b}", _body) for b in e["bullets"]]
    if r.get("projects"):
        main.append(Paragraph("Projects", _h))
        main += [Paragraph(f"- {p}", _body) for p in r["projects"]]
    doc.build([*side, FrameBreak(), *main])


def render_docx_table(r: dict, path: Path) -> None:
    d = docx.Document()
    d.core_properties.author = r["name"]
    d.add_heading(r["name"], level=1)
    d.add_paragraph(f"{r['email']} | {r['phone']} | {r['location']}")
    rows = [("Summary", r["summary"])]
    for e in r["experience"]:
        body = "\n".join([f"{e['title']}, {e['company']}", e["dates"], *e["bullets"]])
        rows.append(("Experience", body))
    if r.get("projects"):
        rows.append(("Projects", "\n".join(r["projects"])))
    rows.append(("Skills", r["skills_text"]))
    rows.append(("Education", "\n".join(r["education"])))
    table = d.add_table(rows=0, cols=2)
    for label, text in rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = text
    d.save(str(path))


def render_docx_caps(r: dict, path: Path) -> None:
    d = docx.Document()
    d.core_properties.author = r["name"]
    p = d.add_paragraph()
    p.add_run(r["name"].upper()).bold = True
    d.add_paragraph(f"{r['location']} · {r['phone']} · {r['email']}")

    def heading(text: str) -> None:
        d.add_paragraph().add_run(text).bold = True

    heading("PROFILE")
    d.add_paragraph(r["summary"])
    heading("PROFESSIONAL EXPERIENCE")
    for e in r["experience"]:
        d.add_paragraph().add_run(f"{e['title']} — {e['company']}").bold = True
        d.add_paragraph(_dates(e, " to "))
        for b in e["bullets"]:
            d.add_paragraph(f"• {b}")
    if r.get("projects"):
        heading("PROJECTS")
        for pr in r["projects"]:
            d.add_paragraph(f"• {pr}")
    heading("TECHNICAL SKILLS")
    d.add_paragraph(r["skills_text"])
    heading("EDUCATION")
    for ed in r["education"]:
        d.add_paragraph(ed)
    d.save(str(path))


RENDERERS = {
    "pdf_classic": render_pdf,
    "pdf_two_column": render_two_column,
    "docx_table": render_docx_table,
    "docx_caps": render_docx_caps,
}


def main() -> None:
    resumes = json.loads((HERE / "resumes.json").read_text(encoding="utf-8"))
    FILES.mkdir(exist_ok=True)
    VARIANTS.mkdir(exist_ok=True)
    for r in resumes:
        RENDERERS[r["format"]](r, FILES / f"{r['key']}.{EXT[r['format']]}")
        if r["key"] in INVARIANCE_SUBSET:
            for layout, render in RENDERERS.items():
                render(r, VARIANTS / f"{r['key']}-{layout}.{EXT[layout]}")
    print(f"rendered {len(resumes)} resumes and {len(INVARIANCE_SUBSET) * 4} variants")


if __name__ == "__main__":
    main()
