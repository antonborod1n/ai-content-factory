"""ContentGapAnalyst protocol — competitor inventory → content-plan topics."""

from __future__ import annotations

from typing import Protocol

from app.schemas.competitor_topics import ContentGapInput, ContentGapOutput


class ContentGapAnalyst(Protocol):
    """Turns extracted competitor hits into a rewritten content plan."""

    async def analyze(self, request: ContentGapInput) -> ContentGapOutput:
        """Return improved topics grounded in the hit list."""
        ...
