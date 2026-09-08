"""Normalize SEO URL slugs from model output or topic fallback."""

from __future__ import annotations

import re
import uuid

_SLUG_SAFE_RE = re.compile(r"[^a-z0-9\-]+")
_DASHES_RE = re.compile(r"-{2,}")


def normalize_url_slug(
    raw: str | None,
    *,
    article_id: uuid.UUID,
    max_length: int = 120,
) -> str:
    """Return a lowercase latin slug; fall back to ``article-<id>`` if empty."""
    cleaned = (raw or "").strip().lower().replace("_", "-").replace(" ", "-")
    cleaned = _SLUG_SAFE_RE.sub("-", cleaned)
    cleaned = _DASHES_RE.sub("-", cleaned).strip("-")
    if cleaned:
        return cleaned[:max_length].rstrip("-")
    return f"article-{article_id.hex[:8]}"
