"""FactChecker protocol — review a writer draft against known sources."""

from __future__ import annotations

from typing import Protocol

from app.schemas.pipeline import FactCheckInput, FactCheckOutput


class FactChecker(Protocol):
    """Flags unsupported or contradictory claims. AI layer only."""

    async def review(self, request: FactCheckInput) -> FactCheckOutput:
        """Return a verdict and short issues. Do not rewrite the article."""
        ...
