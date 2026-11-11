"""Load and merge article topics from a local file (client / batch tooling).

Parsing only — no HTTP, OpenAI, or database access.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.topic_candidates import normalize_topic_text
from app.schemas.articles import ArticleGenerateRequest

# Filled by Stage 3 research, not stored as stubs in a research-linked brief.
RESEARCH_DERIVED_FIELDS = frozenset(
    {
        "word_count",
        "article_goal",
        "outline",
        "include_tables",
        "include_lists",
        "include_faq",
        "faq_count",
        "image_placeholders",
        "infographic_placeholders",
        "section_image_placeholders",
        "cta",
    }
)


def load_topics(path: Path | str) -> list[dict[str, Any]]:
    """Parse a topics file into API request body dicts.

    Supported formats:

    - ``.json`` — array of brief objects (see ``topics/topics.example.json``)
      or legacy strings / objects with ``topic`` (+ optional ``keywords``)
    - ``.txt`` / ``.md`` — one topic per line; ``#`` starts a comment
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    text = file_path.read_text(encoding="utf-8")

    if suffix == ".json":
        return _from_json(text)
    if suffix in {".txt", ".md"}:
        return _from_lines(text)
    raise ValueError(
        f"Unsupported topics file type {suffix!r}; use .json, .txt or .md"
    )


def _from_json(text: str) -> list[dict[str, Any]]:
    raw = json.loads(text)
    if not isinstance(raw, list):
        raise ValueError("JSON topics file must be an array")
    topics: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if isinstance(item, str):
            topic = item.strip()
            if not topic:
                raise ValueError(f"Empty topic string at index {index}")
            topics.append({"topic": topic})
            continue
        if not isinstance(item, dict):
            raise ValueError(
                f"Topic entry at index {index} must be a string or object"
            )
        try:
            validated = ArticleGenerateRequest.model_validate(item)
        except ValidationError as exc:
            raise ValueError(
                f"Invalid topic brief at index {index}: {exc}"
            ) from exc
        topics.append(dump_topic_brief(validated, source=item))
    if not topics:
        raise ValueError("Topics file is empty")
    return topics


def dump_topic_brief(
    request: ArticleGenerateRequest,
    *,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """JSON brief for topics files.

    Research-derived fields stay only when they were already in ``source``
    (so a filled ``topics.json`` is sent to generate as-is).
    """
    data = request.model_dump(mode="json", exclude_none=True)
    research_linked = (
        request.research_id is not None or request.use_competitor_research
    )
    if research_linked:
        kept = source or {}
        for key in RESEARCH_DERIVED_FIELDS:
            if key not in kept:
                data.pop(key, None)
            elif key == "cta" and not str(kept.get("cta") or "").strip():
                data.pop("cta", None)
            elif key == "section_image_placeholders" and not kept.get(key):
                data.pop(key, None)
    elif not str(data.get("cta") or "").strip():
        data.pop("cta", None)
    return data


def apply_content_flags(
    payload: dict[str, Any],
    *,
    text_only: bool = False,
    images_only: bool = False,
    article_id: str | None = None,
) -> dict[str, Any]:
    """Force text-only or images-only generate flags."""
    if not text_only and not images_only and not article_id:
        return payload
    updated = dict(payload)
    if text_only:
        updated["use_text"] = True
        updated["use_images"] = False
    if images_only:
        updated["use_text"] = False
        updated["use_images"] = True
    if article_id:
        updated["article_id"] = article_id
    return updated


def apply_use_dzen(
    payload: dict[str, Any], enabled: bool | None
) -> dict[str, Any]:
    """Return a copy with ``use_dzen`` set when the caller forces a value."""
    if enabled is None:
        return payload
    updated = dict(payload)
    updated["use_dzen"] = enabled
    return updated


@dataclass(frozen=True)
class TopicsMergeResult:
    """Outcome of appending briefs to a topics JSON file."""

    path: Path
    added: int
    skipped: int


def merge_topics(
    path: Path | str,
    new_briefs: list[dict[str, Any]] | list[ArticleGenerateRequest],
) -> TopicsMergeResult:
    """Append unique briefs to a JSON topics file.

    Existing entries are never overwritten. A brief is skipped when its
    normalized ``topic`` already appears in the file.
    """
    file_path = Path(path)
    existing = _load_existing_json(file_path)
    seen = {
        normalize_topic_text(str(item.get("topic") or ""))
        for item in existing
        if isinstance(item, dict)
    }
    seen.discard("")

    added = 0
    skipped = 0
    for raw in new_briefs:
        if isinstance(raw, ArticleGenerateRequest):
            validated = raw
        else:
            try:
                validated = ArticleGenerateRequest.model_validate(raw)
            except ValidationError as exc:
                raise ValueError(f"Invalid topic brief: {exc}") from exc
        key = normalize_topic_text(validated.topic)
        if not key or key in seen:
            skipped += 1
            continue
        source = (
            None
            if isinstance(raw, ArticleGenerateRequest)
            else raw
        )
        existing.append(dump_topic_brief(validated, source=source))
        seen.add(key)
        added += 1

    if not existing:
        raise ValueError("Topics file is empty after merge")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return TopicsMergeResult(path=file_path, added=added, skipped=skipped)


def _load_existing_json(file_path: Path) -> list[dict[str, Any]]:
    if not file_path.exists():
        return []
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("JSON topics file must be an array")
    topics: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if isinstance(item, str):
            topic = item.strip()
            if not topic:
                raise ValueError(f"Empty topic string at index {index}")
            topics.append({"topic": topic})
            continue
        if not isinstance(item, dict):
            raise ValueError(
                f"Topic entry at index {index} must be a string or object"
            )
        topics.append(item)
    return topics


def _from_lines(text: str) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        topics.append({"topic": stripped})
    if not topics:
        raise ValueError("Topics file has no topics")
    return topics
