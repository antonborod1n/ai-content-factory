"""Extract plain text from knowledge-base documents."""

from __future__ import annotations

import io
from dataclasses import dataclass

from app.core.exceptions import DocumentParseError

_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_TEXT_SUFFIXES = {".txt", ".text"}
_PDF_SUFFIXES = {".pdf"}

_MARKDOWN_TYPES = {"text/markdown", "text/x-markdown"}
_TEXT_TYPES = {"text/plain"}
_PDF_TYPES = {"application/pdf"}


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Normalized text extracted from an uploaded or pasted document."""

    title: str
    source: str
    content_type: str
    text: str


def parse_text_document(
    *,
    content: str,
    title: str,
    filename: str = "",
    content_type: str | None = None,
) -> ParsedDocument:
    """Parse a UTF-8 text or markdown body already decoded by the API."""
    text = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise DocumentParseError("Document content is empty")
    resolved_type = _resolve_text_type(filename, content_type)
    return ParsedDocument(
        title=_title_from(title, filename, text),
        source=filename.strip(),
        content_type=resolved_type,
        text=text,
    )


def parse_binary_document(
    *,
    data: bytes,
    filename: str,
    title: str = "",
    content_type: str | None = None,
) -> ParsedDocument:
    """Parse uploaded bytes (markdown, plain text, or PDF)."""
    if not data:
        raise DocumentParseError("Uploaded file is empty")
    suffix = _suffix(filename)
    resolved_type = (content_type or "").split(";")[0].strip().lower()

    if suffix in _PDF_SUFFIXES or resolved_type in _PDF_TYPES:
        text = _extract_pdf_text(data)
        return ParsedDocument(
            title=_title_from(title, filename, text),
            source=filename.strip(),
            content_type="application/pdf",
            text=text,
        )

    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentParseError(
            "File is not valid UTF-8 text and is not a supported PDF"
        ) from exc
    return parse_text_document(
        content=decoded,
        title=title,
        filename=filename,
        content_type=content_type,
    )


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentParseError("PDF parser is not available") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise DocumentParseError("Could not parse PDF file") from exc

    text = "\n\n".join(part.strip() for part in pages if part and part.strip())
    if not text:
        raise DocumentParseError("PDF contains no extractable text")
    return text


def _resolve_text_type(filename: str, content_type: str | None) -> str:
    suffix = _suffix(filename)
    declared = (content_type or "").split(";")[0].strip().lower()
    if suffix in _MARKDOWN_SUFFIXES or declared in _MARKDOWN_TYPES:
        return "text/markdown"
    if suffix in _TEXT_SUFFIXES or declared in _TEXT_TYPES:
        return "text/plain"
    if declared in _PDF_TYPES or suffix in _PDF_SUFFIXES:
        return "application/pdf"
    return "text/markdown" if not declared else declared


def _suffix(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def _title_from(title: str, filename: str, text: str) -> str:
    cleaned = title.strip()
    if cleaned:
        return cleaned
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip()
    if name:
        return name.rsplit(".", 1)[0] or name
    first_line = text.split("\n", 1)[0].lstrip("#").strip()
    return first_line[:120] if first_line else "Untitled document"
