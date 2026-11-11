"""Humanizer protocol — more natural wording, same facts."""

from __future__ import annotations

from typing import Protocol

from app.schemas.ai import AIArticleOutput
from app.schemas.quality import HumanizerInput


class Humanizer(Protocol):
    """Rewrites a draft to sound less templated. AI layer only."""

    async def humanize(self, request: HumanizerInput) -> AIArticleOutput:
        """Return a full article JSON. Preserve images and internal links."""
        ...
