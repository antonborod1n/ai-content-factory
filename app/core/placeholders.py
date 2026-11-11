"""Parse and replace Stage 1 image/infographic placeholder tokens."""

from __future__ import annotations

import re
from dataclasses import dataclass

COVER_TOKEN = "COVER_PLACEHOLDER"
COVER_PATH = "images/cover.png"

_PLACEHOLDER_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\("
    r"(?P<token>(?:"
    r"IMAGE_PLACEHOLDER_(?P<image_n>\d+)"
    r"|INFOGRAPHIC_PLACEHOLDER_(?P<infographic_n>\d+)"
    r"|DZEN_COVER_PLACEHOLDER"
    r"|DZEN_IMAGE_PLACEHOLDER_(?P<dzen_n>\d+)"
    r"|COVER_PLACEHOLDER"
    r"))\)"
)
_ASSET_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\("
    r"(?P<token>images/(?:"
    r"dzen-cover"
    r"|cover"
    r"|(?P<file_kind>image|infographic|dzen)-(?P<file_n>\d+)"
    r")\.png)\)"
)
_HEADING_LINE_RE = re.compile(r"^(#{1,4})\s+(?P<title>.+?)\s*$", re.MULTILINE)
_BOLD_HEADING_RE = re.compile(r"^\*\*(.+)\*\*$")
_EXCERPT_LIMIT = 320


@dataclass(frozen=True)
class ContentPlaceholder:
    """One `![alt](IMAGE_PLACEHOLDER_N)` (or infographic) occurrence."""

    alt: str
    token: str
    kind: str
    number: int
    heading: str = ""
    excerpt: str = ""


def find_placeholders(markdown: str) -> list[ContentPlaceholder]:
    """Return image slots in document order. Duplicate tokens are kept once.

    Matches writer tokens and already-replaced ``images/*.png`` links so
    images can be regenerated without rewriting the article. Each slot
    keeps the nearest heading and a short excerpt of that block.
    """
    text = markdown or ""
    blocks = _markdown_blocks(text)
    found: list[tuple[int, ContentPlaceholder]] = []
    seen: set[str] = set()
    for match in _PLACEHOLDER_RE.finditer(text):
        token = match.group("token")
        if token in seen:
            continue
        seen.add(token)
        kind, number = _kind_and_number(match)
        heading, excerpt = _block_at(blocks, match.start())
        found.append(
            (
                match.start(),
                _placeholder(match, token, kind, number, heading, excerpt),
            )
        )
    for match in _ASSET_RE.finditer(text):
        token = match.group("token")
        if token in seen:
            continue
        seen.add(token)
        kind, number = _asset_kind_and_number(match)
        heading, excerpt = _block_at(blocks, match.start())
        found.append(
            (
                match.start(),
                _placeholder(match, token, kind, number, heading, excerpt),
            )
        )
    found.sort(key=lambda item: item[0])
    return [item for _, item in found]


def _placeholder(
    match: re.Match[str],
    token: str,
    kind: str,
    number: int,
    heading: str,
    excerpt: str,
) -> ContentPlaceholder:
    return ContentPlaceholder(
        alt=(match.group("alt") or "").strip(),
        token=token,
        kind=kind,
        number=number,
        heading=heading,
        excerpt=excerpt,
    )


def _markdown_blocks(text: str) -> list[tuple[int, int, str, str]]:
    """(start, end, heading, body) spans covering the whole document."""
    matches = list(_HEADING_LINE_RE.finditer(text))
    if not matches:
        return [(0, len(text), "", text)]
    blocks: list[tuple[int, int, str, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()]
        blocks.append((0, matches[0].start(), "", preamble))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading = _clean_heading(match.group("title"))
        body = text[match.end() : end]
        blocks.append((match.start(), end, heading, body))
    return blocks


def _block_at(
    blocks: list[tuple[int, int, str, str]], position: int
) -> tuple[str, str]:
    for start, end, heading, body in blocks:
        if start <= position < end:
            return heading, _excerpt(body)
    if blocks:
        heading, body = blocks[-1][2], blocks[-1][3]
        return heading, _excerpt(body)
    return "", ""


def _clean_heading(title: str) -> str:
    cleaned = " ".join((title or "").split())
    bold = _BOLD_HEADING_RE.match(cleaned)
    if bold:
        return bold.group(1).strip()
    return cleaned


def _excerpt(body: str, *, limit: int = _EXCERPT_LIMIT) -> str:
    parts: list[str] = []
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("!["):
            continue
        parts.append(stripped)
    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0]
    return f"{clipped}…"


def _kind_and_number(match: re.Match[str]) -> tuple[str, int]:
    if match.group("infographic_n") is not None:
        return "infographic", int(match.group("infographic_n"))
    if match.group("dzen_n") is not None:
        return "dzen", int(match.group("dzen_n"))
    if match.group("token") == "DZEN_COVER_PLACEHOLDER":
        return "cover", 0
    if match.group("token") == COVER_TOKEN:
        return "hero", 0
    return "image", int(match.group("image_n") or 0)


def _asset_kind_and_number(match: re.Match[str]) -> tuple[str, int]:
    if match.group("token") == "images/dzen-cover.png":
        return "cover", 0
    if match.group("token") == COVER_PATH:
        return "hero", 0
    kind = match.group("file_kind") or "image"
    return kind, int(match.group("file_n") or 0)


def asset_relative_path(kind: str, number: int) -> str:
    """Relative path inside the article folder, e.g. ``images/image-1.png``."""
    if kind == "hero":
        return COVER_PATH
    if kind == "cover":
        return "images/dzen-cover.png"
    if kind == "dzen":
        return f"images/dzen-{number}.png"
    prefix = "infographic" if kind == "infographic" else "image"
    return f"images/{prefix}-{number}.png"


def has_cover_slot(markdown: str) -> bool:
    """True when the article already has a hero token or ``images/cover.png``."""
    text = markdown or ""
    return f"]({COVER_TOKEN})" in text or f"]({COVER_PATH})" in text


def ensure_cover_placeholder(markdown: str, *, title: str) -> str:
    """Put ``COVER_PLACEHOLDER`` right after the H1 when the hero slot is missing."""
    text = markdown or ""
    if has_cover_slot(text):
        return text
    alt = " ".join((title or "").split()) or "Главная"
    block = f"![{alt}]({COVER_TOKEN})\n\n"
    heading = re.search(r"^#\s+.+$", text, re.MULTILINE)
    if heading is None:
        return block + text
    rest = text[heading.end() :]
    return f"{text[: heading.end()]}\n\n{block}{rest.lstrip('\n')}"


def replace_placeholder(markdown: str, token: str, path: str) -> str:
    """Swap the placeholder URL, keeping the original alt text."""
    return (markdown or "").replace(f"]({token})", f"]({path})")
