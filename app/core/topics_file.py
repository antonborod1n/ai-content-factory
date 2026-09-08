"""Load article topics from a local file (client / batch tooling).

Parsing only — no HTTP, OpenAI, or database access.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.articles import ArticleGenerateRequest


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
        # Drop empty optional strings so the HTTP body stays compact, but keep
        # booleans / counts / lists that belong to the brief contract.
        topics.append(
            validated.model_dump(
                mode="json",
                exclude_none=True,
            )
        )
    if not topics:
        raise ValueError("Topics file is empty")
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
