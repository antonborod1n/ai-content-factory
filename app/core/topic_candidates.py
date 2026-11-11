"""Normalize and dedupe Topic Discovery SERP candidates. No AI, no SQL."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

_T = TypeVar("_T")

DEFAULT_JACCARD_THRESHOLD = 0.85


def normalize_topic_text(text: str) -> str:
    """Case-fold and collapse whitespace for comparison."""
    return " ".join(text.casefold().split())


def tokenize_topic(text: str) -> frozenset[str]:
    """Whitespace tokens of the normalized text."""
    normalized = normalize_topic_text(text)
    if not normalized:
        return frozenset()
    return frozenset(normalized.split())


def jaccard_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    """Jaccard index of two token sets. Empty sets are 0."""
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    union = left_set | right_set
    return len(left_set & right_set) / len(union)


def is_near_duplicate(
    text: str,
    existing: Iterable[str],
    *,
    threshold: float = DEFAULT_JACCARD_THRESHOLD,
) -> bool:
    """True when ``text`` matches an existing string exactly or by Jaccard."""
    key = normalize_topic_text(text)
    if not key:
        return True
    tokens = tokenize_topic(text)
    for item in existing:
        if normalize_topic_text(item) == key:
            return True
        if jaccard_similarity(tokens, tokenize_topic(item)) >= threshold:
            return True
    return False


def dedupe_texts(
    texts: Iterable[str],
    *,
    threshold: float = DEFAULT_JACCARD_THRESHOLD,
) -> list[str]:
    """Keep first unique / non-near-duplicate non-empty strings."""
    kept: list[str] = []
    for raw in texts:
        cleaned = " ".join(raw.split())
        if not cleaned:
            continue
        if is_near_duplicate(cleaned, kept, threshold=threshold):
            continue
        kept.append(cleaned)
    return kept


def dedupe_candidates(
    candidates: Iterable[_T],
    *,
    text_attr: str = "text",
    threshold: float = DEFAULT_JACCARD_THRESHOLD,
) -> list[_T]:
    """Keep first candidates whose text is not a near-duplicate."""
    kept: list[_T] = []
    kept_texts: list[str] = []
    for item in candidates:
        raw = getattr(item, text_attr)
        cleaned = " ".join(str(raw).split())
        if not cleaned:
            continue
        if is_near_duplicate(cleaned, kept_texts, threshold=threshold):
            continue
        kept.append(item)
        kept_texts.append(cleaned)
    return kept
