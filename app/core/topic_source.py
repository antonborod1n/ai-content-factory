"""Validate the Discovery vs Competitor-topics switch (no HTTP, AI, or SQL)."""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass


class TopicSourceMode(enum.StrEnum):
    """Where article briefs come from before generate."""

    DISCOVERY = "discovery"
    COMPETITOR = "competitor"


@dataclass(frozen=True, slots=True)
class TopicSourceChoice:
    """Normalized inputs after validation."""

    mode: TopicSourceMode
    seeds: tuple[str, ...]
    files: tuple[str, ...]
    plan: str | None


def split_seeds(*values: str) -> tuple[str, ...]:
    """Flatten repeated --seed values and comma-separated lists."""
    seeds: list[str] = []
    seen: set[str] = set()
    for raw in values:
        for part in raw.split(","):
            item = part.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            seeds.append(item)
    return tuple(seeds)


def validate_topic_source(
    *,
    mode: str,
    seeds: Sequence[str] = (),
    files: Sequence[str] = (),
    plan: str | None = None,
) -> TopicSourceChoice:
    """Require an explicit mode and reject mixed or empty inputs.

    Raises:
        ValueError: missing mode, wrong inputs for the mode, or mixed sources.
    """
    cleaned_mode = (mode or "").strip().lower()
    if not cleaned_mode:
        raise ValueError("mode is required: discovery or competitor")
    try:
        chosen = TopicSourceMode(cleaned_mode)
    except ValueError:
        raise ValueError("mode must be discovery or competitor") from None

    cleaned_seeds = tuple(item.strip() for item in seeds if item and item.strip())
    cleaned_files = tuple(item.strip() for item in files if item and item.strip())
    cleaned_plan = (plan or "").strip() or None

    if chosen is TopicSourceMode.DISCOVERY:
        if cleaned_files or cleaned_plan:
            raise ValueError("discovery mode does not accept --files or --plan")
        if not cleaned_seeds:
            raise ValueError("discovery mode requires at least one --seed")
        return TopicSourceChoice(
            mode=chosen, seeds=cleaned_seeds, files=(), plan=None
        )

    if cleaned_seeds:
        raise ValueError("competitor mode does not accept --seed")
    if cleaned_files and cleaned_plan:
        raise ValueError("competitor mode accepts --files or --plan, not both")
    if not cleaned_files and not cleaned_plan:
        raise ValueError("competitor mode requires --files or --plan")
    return TopicSourceChoice(
        mode=chosen, seeds=(), files=cleaned_files, plan=cleaned_plan
    )
