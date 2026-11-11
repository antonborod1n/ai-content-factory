"""SerpSnapshotProvider: Google/Yandex SERP snapshots. No business rules, no SQL."""

from __future__ import annotations

from typing import Protocol

from app.schemas.discovery import SearchEngine, SerpSnapshot


class SerpSnapshotProvider(Protocol):
    """External SERP snapshot. Implementations must not log API keys."""

    def is_configured(self, engine: SearchEngine) -> bool:
        """True when the engine can be queried with the current settings."""
        ...

    async def snapshot(
        self,
        query: str,
        *,
        engine: SearchEngine,
        top_n: int = 20,
    ) -> SerpSnapshot:
        """Return organic hits plus PAA / related searches."""
        ...
