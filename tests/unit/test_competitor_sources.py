"""Tests for competitor dump parsing (xlsx/csv/txt/json)."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.core.competitor_sources import (
    extract_topic_hits,
    parse_competitor_file,
    topic_from_url,
)
from app.core.exceptions import CompetitorTopicsParseError


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    """Minimal OOXML workbook using inline strings (no openpyxl)."""
    sheet_rows: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells: list[str] = []
        for col_index, value in enumerate(row):
            col = chr(65 + col_index)
            escaped = (
                value.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            cells.append(
                f'<c r="{col}{row_index}" t="inlineStr"><is><t>{escaped}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    workbook = """<?xml version="1.0"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    rels = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    sheet = (
        '<?xml version="1.0"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def test_topic_from_url_skips_service_and_pagination() -> None:
    assert topic_from_url("https://promatras.by/kak-vybrat-matras") == "kak vybrat matras"
    assert topic_from_url("https://promatras.by/catalog") is None
    assert topic_from_url("https://promatras.by/contacts") is None
    assert topic_from_url("https://promatras.by/blog/page-2") is None


def test_parse_csv_keywords() -> None:
    data = "keyword\nкакой матрас выбрать\nжесткость матраса\n".encode("utf-8")
    parsed = parse_competitor_file(data=data, filename="promatras.csv")
    hits = extract_topic_hits(parsed)
    texts = [item.text for item in hits]
    assert "какой матрас выбрать" in texts
    assert "жесткость матраса" in texts
    assert parsed.competitor == "promatras"


def test_parse_txt_urls_filters_service_pages() -> None:
    data = (
        "https://askona.by/ortopedicheskiy-matras\n"
        "https://askona.by/catalog\n"
        "https://askona.by/kak-vybrat-zhestkost\n"
    ).encode("utf-8")
    hits = extract_topic_hits(parse_competitor_file(data=data, filename="askona.txt"))
    texts = [item.text for item in hits]
    assert "ortopedicheskiy matras" in texts
    assert "kak vybrat zhestkost" in texts
    assert not any(item.text == "catalog" for item in hits)


def test_parse_json_url_dump() -> None:
    data = b'{"urls": ["https://promatras.by/bespruzhinnye-matrasy"]}'
    hits = extract_topic_hits(parse_competitor_file(data=data, filename="dump.json"))
    assert hits[0].text == "bespruzhinnye matrasy"
    assert hits[0].kind == "url"


def test_parse_xlsx_urls() -> None:
    data = _xlsx_bytes(
        [
            ["url"],
            ["https://promatras.by/kakoj-matras-vybrat"],
            ["https://promatras.by/about"],
        ]
    )
    hits = extract_topic_hits(parse_competitor_file(data=data, filename="promatras.xlsx"))
    texts = [item.text for item in hits]
    assert "kakoj matras vybrat" in texts
    assert "about" not in texts


def test_empty_file_raises() -> None:
    with pytest.raises(CompetitorTopicsParseError):
        parse_competitor_file(data=b"", filename="empty.csv")


def test_unsupported_type_raises() -> None:
    with pytest.raises(CompetitorTopicsParseError):
        parse_competitor_file(data=b"not a pdf", filename="dump.pdf")


def test_dedupes_near_duplicate_keywords() -> None:
    data = "какой матрас выбрать\nматрас какой выбрать\n".encode("utf-8")
    hits = extract_topic_hits(parse_competitor_file(data=data, filename="keys.txt"))
    assert len(hits) == 1
