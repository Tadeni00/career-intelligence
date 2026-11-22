"""Document text extraction and DOCX rendering."""

from __future__ import annotations

import io
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from app.schemas import (
    TailoredCVContent,
    TailoredEducation,
    TailoredExperience,
    TailoredProject,
)

MAX_EXTRACTED_CHARS = 400_000


class DocumentExtractionError(ValueError):
    """Raised when a document cannot be read or contains no usable text."""


def extract_pdf_text(data: bytes) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise DocumentExtractionError("PDF support requires PyMuPDF.") from exc

    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - library raises many types
        raise DocumentExtractionError("The PDF could not be opened; it may be corrupt.") from exc

    try:
        if document.page_count == 0:
            raise DocumentExtractionError("The PDF has no pages.")
        parts: list[str] = []
        for page in document:
            parts.append(page.get_text("text"))
            if sum(len(p) for p in parts) > MAX_EXTRACTED_CHARS:
                break
        text = "\n".join(parts).strip()
    finally:
        document.close()

    if not text.strip():
        raise DocumentExtractionError(
            "No text could be extracted. The PDF may be a scanned image, which V1 does not OCR."
        )
    return text[:MAX_EXTRACTED_CHARS]


def extract_docx_text(data: bytes) -> str:
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise DocumentExtractionError("The DOCX could not be opened; it may be corrupt.") from exc

    blocks: list[str] = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))

    text = "\n".join(blocks).strip()
    if not text:
        raise DocumentExtractionError("The DOCX contains no text.")
    return text[:MAX_EXTRACTED_CHARS]


def extract_text(data: bytes, file_type: str) -> str:
    if file_type == "pdf":
        return extract_pdf_text(data)
    if file_type == "docx":
        return extract_docx_text(data)
    raise DocumentExtractionError(f"Unsupported document type '{file_type}'.")


def extract_text_from_path(path: str, file_type: str) -> str:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise DocumentExtractionError(f"Stored document could not be read: {exc}") from exc
    return extract_text(data, file_type)


# ------------------------------------------------------------------ rendering


def _add_heading(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x1F, 0x2A, 0x37)
    paragraph.paragraph_format.space_before = Pt(10)
    paragraph.paragraph_format.space_after = Pt(4)


def _add_bullets(document: Document, bullets: list[str]) -> None:
    for bullet in bullets:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.add_run(bullet)


def render_tailored_cv_docx(content: TailoredCVContent, candidate_name: str) -> bytes:
    """Render tailored CV content into a DOCX byte string."""
    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    name_paragraph = document.add_paragraph()
    name_run = name_paragraph.add_run(candidate_name or "Curriculum Vitae")
    name_run.bold = True
    name_run.font.size = Pt(18)
    name_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

    if content.summary:
        document.add_paragraph(content.summary)

    if content.skills:
        _add_heading(document, "Skills")
        document.add_paragraph(", ".join(content.skills))

    if content.experience:
        _add_heading(document, "Experience")
        for item in content.experience:
            _render_experience(document, item)

    if content.projects:
        _add_heading(document, "Projects")
        for project in content.projects:
            _render_project(document, project)

    if content.education:
        _add_heading(document, "Education")
        for education in content.education:
            _render_education(document, education)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _render_experience(document: Document, item: TailoredExperience) -> None:
    period = f"{item.start_date or ''} – {item.end_date or 'Present'}".strip(" –")
    header = document.add_paragraph()
    header_run = header.add_run(f"{item.title} — {item.company}")
    header_run.bold = True
    if period:
        period_run = header.add_run(f"  ({period})")
        period_run.italic = True
        period_run.font.size = Pt(9)
    _add_bullets(document, item.bullets)


def _render_project(document: Document, item: TailoredProject) -> None:
    paragraph = document.add_paragraph()
    run = paragraph.add_run(item.name)
    run.bold = True
    if item.technologies:
        tech_run = paragraph.add_run(f"  ({', '.join(item.technologies)})")
        tech_run.italic = True
        tech_run.font.size = Pt(9)
    if item.description:
        document.add_paragraph(item.description)


def _render_education(document: Document, item: TailoredEducation) -> None:
    line = " — ".join(part for part in (item.degree, item.field) if part) or item.institution
    paragraph = document.add_paragraph()
    run = paragraph.add_run(line)
    run.bold = True
    if item.institution and item.degree:
        paragraph.add_run(f"  ({item.institution})")
    if item.end_date:
        end_run = paragraph.add_run(f"  {item.end_date}")
        end_run.italic = True
        end_run.font.size = Pt(9)


def write_docx(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


__all__ = [
    "DocumentExtractionError",
    "extract_docx_text",
    "extract_pdf_text",
    "extract_text",
    "extract_text_from_path",
    "render_tailored_cv_docx",
    "write_docx",
]
