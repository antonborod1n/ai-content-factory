"""SearchProvider: organic SERP results. No business rules, no SQL."""

from __future__ import annotations

from typing import Protocol

from app.schemas.research import SearchHit


class SearchProvider(Protocol):
    """External web search. Implementations must not log API keys."""

    async def search(self, query: str, *, top_n: int = 5) -> list[SearchHit]:
        """Return ranked organic hits for the query."""
        ...
