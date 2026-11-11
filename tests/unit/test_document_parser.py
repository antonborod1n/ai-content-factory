"""Unit tests for knowledge-base document parsing."""

import pytest

from app.core.document_parser import parse_binary_document, parse_text_document
from app.core.exceptions import DocumentParseError


def test_parse_markdown_uses_filename_title() -> None:
    parsed = parse_text_document(
        content="# Насос\n\nВыбирайте по напору.",
        title="",
        filename="pumps.md",
    )
    assert parsed.title == "pumps"
    assert parsed.content_type == "text/markdown"
    assert "напору" in parsed.text


def test_parse_rejects_blank_content() -> None:
    with pytest.raises(DocumentParseError, match="empty"):
        parse_text_document(content="  \n", title="T")


def test_parse_plain_text_from_txt_filename() -> None:
    parsed = parse_text_document(
        content="Hello pumps",
        title="Spec",
        filename="notes.txt",
    )
    assert parsed.title == "Spec"
    assert parsed.content_type == "text/plain"


def test_parse_binary_utf8_markdown() -> None:
    parsed = parse_binary_document(
        data=b"# Title\n\nBody",
        filename="guide.md",
        title="",
    )
    assert parsed.content_type == "text/markdown"
    assert parsed.text.startswith("# Title")


def test_parse_binary_rejects_empty() -> None:
    with pytest.raises(DocumentParseError, match="empty"):
        parse_binary_document(data=b"", filename="x.md")


def test_parse_invalid_pdf_is_safe_error() -> None:
    with pytest.raises(DocumentParseError, match="PDF"):
        parse_binary_document(data=b"%PDF-not-a-real-file", filename="doc.pdf")
