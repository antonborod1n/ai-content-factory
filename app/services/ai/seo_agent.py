"""SeoAgent protocol — refine outline and SEO wrapper after research."""

from __future__ import annotations

from typing import Protocol

from app.schemas.pipeline import SeoPlanInput, SeoPlanOutput


class SeoAgent(Protocol):
    """Turns a brief (+ competitor notes) into a stronger SEO plan. AI layer only."""

    async def plan(self, request: SeoPlanInput) -> SeoPlanOutput:
        """Return outline and keyword/meta hints; never copy competitor body text."""
        ...
