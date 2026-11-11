"""Deterministic internal-link insertion (no AI, no SQL)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MIN_ANCHOR_LENGTH = 4
_HEADING_RE = re.compile(r"^#{1,6} .*$", re.MULTILINE)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")


@dataclass(frozen=True)
class LinkTarget:
    """Another completed article that may be linked."""

    title: str
    url_slug: str
    topic: str = ""
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class InsertedLink:
    """One markdown link that was written into the body."""

    title: str
    url_slug: str
    anchor: str


def score_target(
    target: LinkTarget, *, keywords: list[str], topic: str
) -> int:
    """Higher score = more overlapping keywords / topic tokens."""
    source_terms = {_norm(item) for item in (*keywords, *topic.split()) if _norm(item)}
    target_terms = {
        _norm(item)
        for item in (*target.keywords, *target.topic.split(), *target.title.split())
        if _norm(item)
    }
    overlap = source_terms & target_terms
    return sum(2 if len(term) >= 6 else 1 for term in overlap)


def insert_internal_links(
    markdown: str,
    targets: list[LinkTarget],
    *,
    keywords: list[str],
    topic: str,
    max_links: int = 5,
    href_prefix: str = "/",
) -> tuple[str, list[InsertedLink]]:
    """Insert up to ``max_links`` markdown links. Skip headings, images, links."""
    if max_links <= 0 or not markdown.strip() or not targets:
        return markdown, []

    ranked = sorted(
        (
            (score_target(target, keywords=keywords, topic=topic), target)
            for target in targets
            if target.url_slug.strip()
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    updated = markdown
    inserted: list[InsertedLink] = []
    used_slugs: set[str] = set()

    for score, target in ranked:
        if score <= 0 or len(inserted) >= max_links:
            continue
        slug = target.url_slug.strip()
        if slug in used_slugs:
            continue
        anchor = _pick_anchor(updated, target, keywords=keywords)
        if anchor is None:
            continue
        href = _href(href_prefix, slug)
        replaced = _replace_first_plain(updated, anchor, href)
        if replaced is None:
            continue
        updated = replaced
        used_slugs.add(slug)
        inserted.append(
            InsertedLink(title=target.title, url_slug=slug, anchor=anchor)
        )
    return updated, inserted


def _href(prefix: str, slug: str) -> str:
    cleaned = (prefix or "/").strip() or "/"
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return f"{cleaned.rstrip('/')}/{slug}"


def _pick_anchor(
    markdown: str,
    target: LinkTarget,
    *,
    keywords: list[str],
) -> str | None:
    candidates: list[str] = []
    for item in (*keywords, *target.keywords, target.title, target.topic):
        cleaned = item.strip()
        if len(cleaned) >= _MIN_ANCHOR_LENGTH:
            candidates.append(cleaned)
    candidates.sort(key=len, reverse=True)
    protected = _protected_ranges(markdown)
    for anchor in candidates:
        match = _search_plain(markdown, anchor, protected)
        if match is not None:
            return markdown[match[0] : match[1]]
    return None


def _replace_first_plain(markdown: str, anchor: str, href: str) -> str | None:
    protected = _protected_ranges(markdown)
    span = _search_plain(markdown, anchor, protected)
    if span is None:
        return None
    start, end = span
    return f"{markdown[:start]}[{markdown[start:end]}]({href}){markdown[end:]}"


def _search_plain(
    markdown: str, anchor: str, protected: list[tuple[int, int]]
) -> tuple[int, int] | None:
    pattern = re.compile(rf"(?<!\w)({re.escape(anchor)})(?!\w)", re.IGNORECASE)
    for match in pattern.finditer(markdown):
        if _is_protected(match.start(), protected):
            continue
        return match.start(), match.end()
    return None


def _protected_ranges(markdown: str) -> list[tuple[int, int]]:
    ranges = [match.span() for match in _HEADING_RE.finditer(markdown)]
    ranges.extend(match.span() for match in _FENCE_RE.finditer(markdown))
    ranges.extend(match.span() for match in _IMAGE_RE.finditer(markdown))
    ranges.extend(match.span() for match in _LINK_RE.finditer(markdown))
    return ranges


def _is_protected(index: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in ranges)


def _norm(value: str) -> str:
    return value.strip().casefold()
