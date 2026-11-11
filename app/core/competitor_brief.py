"""Derive brief volume / media / FAQ flags from competitor page counts.

Deterministic: no AI, no SQL. Used after Stage 3 research attaches a brief.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

MIN_TARGET_WORDS = 400
MAX_TARGET_WORDS = 8000
MAX_INFOGRAPHICS = 2
DEFAULT_FAQ_COUNT = 5


@dataclass(frozen=True)
class CompetitorCounts:
    """Numeric structure already extracted from one competitor page."""

    word_count: int = 0
    list_count: int = 0
    table_count: int = 0
    has_faq: bool = False
    infographic_count: int = 0


@dataclass(frozen=True)
class CompetitorBriefStats:
    """Values copied onto the article brief after competitor analysis."""

    word_count: int | None
    include_tables: bool
    include_lists: bool
    include_faq: bool
    faq_count: int
    infographic_placeholders: int


def brief_stats_from_competitors(
    pages: Sequence[CompetitorCounts],
) -> CompetitorBriefStats:
    """Majority / average of usable competitor pages. Empty input keeps None."""
    usable = [item for item in pages if _has_signal(item)]
    if not usable:
        return CompetitorBriefStats(
            word_count=None,
            include_tables=False,
            include_lists=False,
            include_faq=False,
            faq_count=0,
            infographic_placeholders=0,
        )

    include_tables = _majority(sum(1 for item in usable if item.table_count > 0), len(usable))
    include_lists = _majority(sum(1 for item in usable if item.list_count > 0), len(usable))
    include_faq = _majority(sum(1 for item in usable if item.has_faq), len(usable))
    return CompetitorBriefStats(
        word_count=_average_word_count(usable),
        include_tables=include_tables,
        include_lists=include_lists,
        include_faq=include_faq,
        faq_count=DEFAULT_FAQ_COUNT if include_faq else 0,
        infographic_placeholders=_infographic_placeholders(usable, include_tables),
    )


def _has_signal(item: CompetitorCounts) -> bool:
    return (
        item.word_count > 0
        or item.list_count > 0
        or item.table_count > 0
        or item.has_faq
        or item.infographic_count > 0
    )


def _majority(hits: int, total: int) -> bool:
    return total > 0 and hits * 2 > total


def _average_word_count(pages: Sequence[CompetitorCounts]) -> int | None:
    samples = [item.word_count for item in pages if item.word_count > 0]
    if not samples:
        return None
    average = int(round(sum(samples) / len(samples)))
    return max(MIN_TARGET_WORDS, min(MAX_TARGET_WORDS, average))


def _infographic_placeholders(
    pages: Sequence[CompetitorCounts], include_tables: bool
) -> int:
    samples = [max(0, item.infographic_count) for item in pages]
    if any(samples):
        average = int(round(sum(samples) / len(samples)))
        return max(0, min(MAX_INFOGRAPHICS, average))
    return 1 if include_tables else 0
