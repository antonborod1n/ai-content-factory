"""DzenWriter protocol — shorter channel version of a completed article."""

from __future__ import annotations

from typing import Protocol

from app.schemas.dzen import DzenArticleOutput, DzenWriteInput


class DzenWriter(Protocol):
    """Creates a shorter Dzen article. AI layer only — no persistence."""

    async def generate(self, request: DzenWriteInput) -> DzenArticleOutput:
        """Return title + markdown sized for Dzen."""
        ...
