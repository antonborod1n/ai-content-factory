"""TopicPlanner protocol — cluster SERP candidates into article briefs."""

from __future__ import annotations

from typing import Protocol

from app.schemas.discovery import TopicPlanInput, TopicPlanOutput


class TopicPlanner(Protocol):
    """Turns SERP candidates into unique article briefs. AI layer only."""

    async def plan(self, request: TopicPlanInput) -> TopicPlanOutput:
        """Return clustered briefs grounded in the candidate list."""
        ...
