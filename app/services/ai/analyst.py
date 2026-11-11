"""CompetitorAnalyst protocol — improved outline from SERP structures."""

from __future__ import annotations

from typing import Protocol

from app.schemas.ai import CompetitorPlanOutput
from app.schemas.research import CompetitorPlanInput


class CompetitorAnalyst(Protocol):
    """Turns competitor profiles into an improved outline. AI layer only."""

    async def plan(self, request: CompetitorPlanInput) -> CompetitorPlanOutput:
        """Return a unique outline; never copy competitor body text."""
        ...
