"""Parse competitor topic dumps (xlsx/csv/txt/json) and extract topic hits.

Deterministic only — no AI, HTTP, or SQL.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

from app.core.exceptions import CompetitorTopicsParseError
from app.core.topic_candidates import dedupe_texts

_URL_RE = re.compile(r"https?://[^\s]+", re.I)
_PATH_RE = re.compile(r"^/.+")
_HEADER_WORD_RE = re.compile(
    r"^(n|id|url|href|title|h1|keyword|query|тема|заголовок|ключ|"
    r"запрос|страница|ссылка|volume|vol|kd|позиция|трафик|source|источник)$",
    re.I,
)
_SERVICE_SLUGS = frozenset(
    {
        "",
        "index",
        "home",
        "glavnaya",
        "contact",
        "contacts",
        "kontakty",
        "about",
        "o-nas",
        "cart",
        "basket",
        "korzina",
        "checkout",
        "login",
        "signin",
        "account",
        "search",
        "poisk",
        "privacy",
        "policy",
        "politika",
        "delivery",
        "dostavka",
        "oplata",
        "payment",
        "tag",
        "tags",
        "catalog",
        "katalog",
        "category",
        "news",
        "novosti",
    }
)
_SOURCE_EXT = {".xlsx", ".xlsm", ".csv", ".tsv", ".txt", ".md", ".json"}
_CELL_MAX = 500


@dataclass(frozen=True, slots=True)
class CompetitorSheet:
    name: str
    guess: str
    headers: list[str]
    rows: list[dict[str, str]]
    sample_urls: list[str]


@dataclass(frozen=True, slots=True)
class ParsedCompetitorFile:
    filename: str
    competitor: str
    guess: str
    sheets: list[CompetitorSheet]


@dataclass(frozen=True, slots=True)
class CompetitorTopicHit:
    text: str
    competitor: str
    kind: str
    source_file: str
    url: str = ""


def parse_competitor_file(*, data: bytes, filename: str) -> ParsedCompetitorFile:
    """Parse one uploaded competitor dump into sheets of cell values."""
    if not data:
        raise CompetitorTopicsParseError("Uploaded file is empty")
    suffix = Path(filename).suffix.lower()
    if suffix not in _SOURCE_EXT:
        raise CompetitorTopicsParseError(
            f"Unsupported competitor file type {suffix!r}; "
            "use .xlsx, .xlsm, .csv, .tsv, .txt, .md or .json"
        )
    if suffix in {".xlsx", ".xlsm"}:
        dumped = _dump_xlsx(data, filename)
    elif suffix == ".csv":
        dumped = _dump_delimited(data, ",", filename)
    elif suffix == ".tsv":
        dumped = _dump_delimited(data, "\t", filename)
    elif suffix == ".json":
        dumped = _dump_json(data, filename)
    else:
        dumped = _dump_text(data, filename)
    return ParsedCompetitorFile(
        filename=Path(filename).name,
        competitor=_competitor_name(filename),
        guess=_guess([value for sheet in dumped for value in _sheet_values(sheet)]),
        sheets=dumped,
    )


def extract_topic_hits(
    parsed: ParsedCompetitorFile,
    *,
    threshold: float = 0.85,
) -> list[CompetitorTopicHit]:
    """Pull URL slugs and keyword phrases; drop service pages and near-dupes."""
    raw: list[CompetitorTopicHit] = []
    for sheet in parsed.sheets:
        competitor = parsed.competitor
        if len(parsed.sheets) > 1 and sheet.name.strip():
            competitor = f"{parsed.competitor}/{sheet.name}"
        for row in sheet.rows:
            for value in row.values():
                raw.extend(
                    _hits_from_cell(
                        value,
                        competitor=competitor,
                        source_file=parsed.filename,
                    )
                )
    unique_texts = dedupe_texts((item.text for item in raw), threshold=threshold)
    allowed = set(unique_texts)
    hits: list[CompetitorTopicHit] = []
    kept: set[str] = set()
    for item in raw:
        key = " ".join(item.text.split())
        if key not in allowed or key in kept:
            continue
        kept.add(key)
        hits.append(item)
    return hits


def _hits_from_cell(
    value: str, *, competitor: str, source_file: str
) -> list[CompetitorTopicHit]:
    text = _cell(value)
    if not text:
        return []
    urls = _URL_RE.findall(text)
    hits: list[CompetitorTopicHit] = []
    for url in urls:
        topic = topic_from_url(url)
        if topic:
            hits.append(
                CompetitorTopicHit(
                    text=topic,
                    competitor=competitor,
                    kind="url",
                    source_file=source_file,
                    url=url.rstrip(").,;"),
                )
            )
    if urls:
        return hits
    if _PATH_RE.match(text) and "-" in text:
        topic = topic_from_url("https://example.com" + text.split("?", 1)[0])
        if topic:
            return [
                CompetitorTopicHit(
                    text=topic,
                    competitor=competitor,
                    kind="url",
                    source_file=source_file,
                    url=text,
                )
            ]
    if _is_keyword_cell(text):
        return [
            CompetitorTopicHit(
                text=text,
                competitor=competitor,
                kind="keyword",
                source_file=source_file,
            )
        ]
    return []


def topic_from_url(url: str) -> str | None:
    """Human-readable topic from a page slug. None for service/pagination URLs."""
    cleaned = url.strip().rstrip(").,;")
    parsed = urlparse(cleaned)
    path = unquote(parsed.path or "")
    parts = [part for part in path.split("/") if part]
    if not parts:
        return None
    last = re.sub(r"\.(html?|php|aspx)$", "", parts[-1], flags=re.I)
    if re.fullmatch(r"(page|p|str)[-_]?\d+", last, flags=re.I) or last.isdigit():
        return None
    if last.casefold() in _SERVICE_SLUGS:
        return None
    words = [word for word in re.split(r"[-_]+", last) if word]
    if not words or (len(words) == 1 and len(words[0]) < 3):
        return None
    return " ".join(words)


def _is_keyword_cell(text: str) -> bool:
    if _URL_RE.search(text):
        return False
    if re.fullmatch(r"\d+([.,]\d+)?", text):
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return False
    if "[" in text and "]" in text and " " not in text:
        return False
    words = text.split()
    if not words or len(words) > 12:
        return False
    if len(text) > 160:
        return False
    return True


def _competitor_name(filename: str) -> str:
    stem = Path(filename).stem.strip()
    return stem or "competitor"


def _cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > _CELL_MAX:
        return text[:497] + "..."
    return text


def _guess(values: list[str]) -> str:
    nonempty = [item for item in values if item]
    if not nonempty:
        return "empty"
    url_hits = 0
    keyword_hits = 0
    for value in nonempty:
        if _URL_RE.search(value) or (_PATH_RE.match(value) and "-" in value):
            url_hits += 1
        elif _is_keyword_cell(value):
            keyword_hits += 1
    n = len(nonempty)
    if url_hits / n >= 0.4:
        return "urls"
    if keyword_hits / n >= 0.5:
        return "keywords"
    return "mixed"


def _sheet_values(sheet: CompetitorSheet) -> list[str]:
    values: list[str] = []
    for row in sheet.rows:
        values.extend(item for item in row.values() if item)
    return values


def _looks_like_header(row: list[str]) -> bool:
    cells = [item for item in row if item]
    if not cells:
        return False
    if any(_URL_RE.match(item) for item in cells):
        return False
    if len(cells) == 1:
        return bool(_HEADER_WORD_RE.match(cells[0]))
    if any("?" in item or len(item.split()) >= 6 for item in cells):
        return False
    short = [item for item in cells if len(item) <= 40 and len(item.split()) <= 4]
    return len(short) == len(cells)


def _unique_header(headers: list[str], index: int, raw: str) -> str:
    base = _cell(raw) or f"col_{index + 1}"
    key = base
    n = 2
    while key in headers:
        key = f"{base}_{n}"
        n += 1
    return key


def _rows_to_objects(grid: list[list[str]]) -> tuple[list[str], list[dict[str, str]]]:
    if not grid:
        return [], []
    header_row = grid[0] if _looks_like_header(grid[0]) else None
    data = grid[1:] if header_row is not None else grid
    width = max((len(row) for row in grid), default=0)
    headers: list[str] = []
    for index in range(width):
        raw = header_row[index] if header_row is not None and index < len(header_row) else ""
        headers.append(_unique_header(headers, index, raw or f"col_{index + 1}"))
    rows: list[dict[str, str]] = []
    for raw in data:
        if not any(raw):
            continue
        rows.append({headers[i]: (raw[i] if i < len(raw) else "") for i in range(width)})
    return headers, rows


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CompetitorTopicsParseError("File is not valid UTF-8 text") from exc


def _dump_delimited(data: bytes, delimiter: str, filename: str) -> list[CompetitorSheet]:
    text = _decode_text(data)
    grid = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    grid = [[_cell(item) for item in row] for row in grid if any(_cell(item) for item in row)]
    if not grid:
        raise CompetitorTopicsParseError(f"No data found in {filename}")
    headers, rows = _rows_to_objects(grid)
    values = [item for row in rows for item in row.values() if item]
    return [
        CompetitorSheet(
            name=Path(filename).name,
            guess=_guess(values),
            headers=headers,
            rows=rows,
            sample_urls=_sample_urls(values),
        )
    ]


def _dump_text(data: bytes, filename: str) -> list[CompetitorSheet]:
    lines = [_cell(line) for line in _decode_text(data).splitlines() if _cell(line)]
    if not lines:
        raise CompetitorTopicsParseError(f"No data found in {filename}")
    rows = [{"line": str(index + 1), "value": line} for index, line in enumerate(lines)]
    return [
        CompetitorSheet(
            name=Path(filename).name,
            guess=_guess(lines),
            headers=["line", "value"],
            rows=rows,
            sample_urls=_sample_urls(lines),
        )
    ]


def _flatten_json(node: object, prefix: str = "") -> list[list[str]]:
    rows: list[list[str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_json(value, next_prefix))
        return rows
    if isinstance(node, list):
        for index, value in enumerate(node):
            next_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            rows.extend(_flatten_json(value, next_prefix))
        return rows
    text = _cell(node)
    if text:
        rows.append([prefix, text])
    return rows


def _dump_json(data: bytes, filename: str) -> list[CompetitorSheet]:
    try:
        payload = json.loads(_decode_text(data))
    except json.JSONDecodeError as exc:
        raise CompetitorTopicsParseError(f"Invalid JSON in {filename}") from exc
    grid = [["path", "value"], *_flatten_json(payload)]
    if len(grid) < 2:
        raise CompetitorTopicsParseError(f"No data found in {filename}")
    headers, rows = _rows_to_objects(grid)
    values = [row.get("value", "") for row in rows if row.get("value")]
    return [
        CompetitorSheet(
            name=Path(filename).name,
            guess=_guess(values),
            headers=headers,
            rows=rows,
            sample_urls=_sample_urls(values),
        )
    ]


def _sample_urls(values: list[str], *, limit: int = 20) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for match in _URL_RE.findall(value):
            if match in seen:
                continue
            seen.add(match)
            out.append(match)
            if len(out) >= limit:
                return out
    return out


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _col_row(ref: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"([A-Z]+)(\d+)", ref, flags=re.I)
    if not match:
        return None
    letters = match.group(1).upper()
    col = 0
    for char in letters:
        col = col * 26 + (ord(char) - 64)
    return col - 1, int(match.group(2)) - 1


def _dump_xlsx(data: bytes, filename: str) -> list[CompetitorSheet]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise CompetitorTopicsParseError(f"{filename} is not a valid .xlsx") from exc
    with archive:
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names:
            raise CompetitorTopicsParseError(f"{filename} is not a valid .xlsx")
        shared = _parse_shared_strings(
            archive.read("xl/sharedStrings.xml").decode("utf-8")
            if "xl/sharedStrings.xml" in names
            else ""
        )
        sheets_meta = _parse_workbook(archive)
        sheets: list[CompetitorSheet] = []
        for name, path in sheets_meta:
            if path not in names:
                continue
            grid = _parse_sheet(archive.read(path).decode("utf-8"), shared)
            if not grid:
                continue
            headers, rows = _rows_to_objects(grid)
            values = [item for row in rows for item in row.values() if item]
            sheets.append(
                CompetitorSheet(
                    name=name,
                    guess=_guess(values),
                    headers=headers,
                    rows=rows,
                    sample_urls=_sample_urls(values),
                )
            )
    if not sheets:
        raise CompetitorTopicsParseError(f"No data found in {filename}")
    return sheets


def _parse_shared_strings(xml: str) -> list[str]:
    if not xml:
        return []
    root = ElementTree.fromstring(xml)
    out: list[str] = []
    for si in root.iter():
        if _local(si.tag) != "si":
            continue
        parts = [
            node.text or ""
            for node in si.iter()
            if _local(node.tag) == "t"
        ]
        out.append(_cell("".join(parts)))
    return out


def _parse_workbook(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    rel_map: dict[str, str] = {}
    if "xl/_rels/workbook.xml.rels" in archive.namelist():
        rel_root = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        )
        for node in rel_root:
            if _local(node.tag) != "Relationship":
                continue
            rel_id = node.attrib.get("Id", "")
            target = node.attrib.get("Target", "").replace("\\", "/")
            if target.startswith("/"):
                target = target.lstrip("/")
            elif not target.startswith("xl/"):
                target = "xl/" + target.removeprefix("./")
            rel_map[rel_id] = target
    wb_root = ElementTree.fromstring(archive.read("xl/workbook.xml").decode("utf-8"))
    sheets: list[tuple[str, str]] = []
    for node in wb_root.iter():
        if _local(node.tag) != "sheet":
            continue
        name = node.attrib.get("name", "").strip()
        rel_id = node.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ) or node.attrib.get("id", "")
        target = rel_map.get(rel_id, "")
        if name and target:
            sheets.append((name, target))
    return sheets


def _parse_sheet(xml: str, shared: list[str]) -> list[list[str]]:
    root = ElementTree.fromstring(xml)
    grid: dict[int, dict[int, str]] = {}
    for cell in root.iter():
        if _local(cell.tag) != "c":
            continue
        ref = cell.attrib.get("r", "")
        pos = _col_row(ref)
        if pos is None:
            continue
        col, row = pos
        cell_type = cell.attrib.get("t", "")
        value = ""
        if cell_type == "s":
            raw = _child_text(cell, "v")
            try:
                value = shared[int(raw)] if raw else ""
            except (ValueError, IndexError):
                value = ""
        elif cell_type == "inlineStr":
            value = _cell(
                "".join(
                    node.text or ""
                    for node in cell.iter()
                    if _local(node.tag) == "t"
                )
            )
        elif cell_type == "b":
            value = "TRUE" if _child_text(cell, "v") == "1" else "FALSE"
        elif cell_type == "e":
            value = ""
        else:
            value = _cell(_child_text(cell, "v"))
        if not value:
            continue
        grid.setdefault(row, {})[col] = value
    rows: list[list[str]] = []
    for row_index in sorted(grid):
        cols = grid[row_index]
        width = max(cols) + 1
        rows.append([cols.get(index, "") for index in range(width)])
    return rows


def _child_text(node: ElementTree.Element, local_name: str) -> str:
    for child in node:
        if _local(child.tag) == local_name:
            return _cell(child.text or "")
    return ""
