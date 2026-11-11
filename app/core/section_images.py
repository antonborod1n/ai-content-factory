"""Allocate photo slots to outline sections from competitor pages.

Deterministic: no AI, no SQL. Used when research attaches a brief, and later
when SEO rewrites the outline.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

MAX_IMAGES_PER_SECTION = 2
MAX_TOTAL_IMAGES = 8
_MIN_HEADING_OVERLAP = 0.28
_TOKEN_RE = re.compile(r"[a-zа-яё0-9]{3,}", re.IGNORECASE)


def heading_tokens(text: str) -> set[str]:
    """Lowercased word tokens used to match our outline to competitor H2s."""
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text or "")}


def heading_similarity(left: str, right: str) -> float:
    """Jaccard overlap of heading tokens. 0 when either side is empty."""
    left_tokens = heading_tokens(left)
    right_tokens = heading_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def allocate_section_images(
    outline: Sequence[str],
    pages: Sequence[Sequence[tuple[str, int]]],
    *,
    page_totals: Sequence[int] | None = None,
) -> list[int]:
    """Average competitor photos per matched heading; leftover fills the rest.

    Returns one count per non-blank outline heading. Empty list means
    “no usable competitor signal — keep the brief defaults”.
    """
    titles = [title.strip() for title in outline if title.strip()]
    if not titles:
        return []

    totals = _page_totals(pages, page_totals)
    if not totals:
        return []
    target = int(round(sum(totals) / len(totals)))
    target = max(0, min(MAX_TOTAL_IMAGES, target))
    if target <= 0:
        return []

    matched: list[int | None] = []
    for title in titles:
        samples = _matched_counts(title, pages)
        if samples:
            matched.append(
                min(
                    MAX_IMAGES_PER_SECTION,
                    int(round(sum(samples) / len(samples))),
                )
            )
        else:
            matched.append(None)

    used = sum(value for value in matched if value is not None)
    leftover = max(0, target - used)
    holes = [index for index, value in enumerate(matched) if value is None]
    result = [value if value is not None else 0 for value in matched]
    if holes and leftover:
        extra = _spread(leftover, len(holes))
        for index, count in zip(holes, extra, strict=True):
            result[index] = min(MAX_IMAGES_PER_SECTION, count)
        leftover = max(0, leftover - sum(extra))

    if leftover:
        for index in range(len(result)):
            room = MAX_IMAGES_PER_SECTION - result[index]
            if room <= 0:
                continue
            take = min(room, leftover)
            result[index] += take
            leftover -= take
            if leftover <= 0:
                break

    if sum(result) > MAX_TOTAL_IMAGES:
        result = _trim(result, MAX_TOTAL_IMAGES)
    return result


def _page_totals(
    pages: Sequence[Sequence[tuple[str, int]]],
    page_totals: Sequence[int] | None,
) -> list[int]:
    totals: list[int] = []
    for index, sections in enumerate(pages):
        if page_totals is not None and index < len(page_totals):
            totals.append(max(0, int(page_totals[index])))
        else:
            totals.append(sum(max(0, int(count)) for _, count in sections))
    return totals


def _matched_counts(
    title: str, pages: Sequence[Sequence[tuple[str, int]]]
) -> list[int]:
    samples: list[int] = []
    for sections in pages:
        best_score = 0.0
        best_count: int | None = None
        for heading, count in sections:
            if not heading.strip():
                continue
            score = heading_similarity(title, heading)
            if score > best_score:
                best_score = score
                best_count = max(0, int(count))
        if best_score >= _MIN_HEADING_OVERLAP and best_count is not None:
            samples.append(best_count)
    return samples


def _spread(total: int, buckets: int) -> list[int]:
    if buckets <= 0 or total <= 0:
        return [0] * max(buckets, 0)
    base, remainder = divmod(total, buckets)
    return [base + (1 if index < remainder else 0) for index in range(buckets)]


def _trim(counts: list[int], limit: int) -> list[int]:
    trimmed = list(counts)
    overflow = sum(trimmed) - limit
    index = len(trimmed) - 1
    while overflow > 0 and index >= 0:
        take = min(trimmed[index], overflow)
        trimmed[index] -= take
        overflow -= take
        index -= 1
    return trimmed
