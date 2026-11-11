"""Route snapshot() calls to the Google or Yandex provider."""

from __future__ import annotations

from app.core.exceptions import DiscoveryConfigurationError
from app.schemas.discovery import SearchEngine, SerpSnapshot
from app.services.discovery.snapshotter import SerpSnapshotProvider


class RoutingSerpSnapshotProvider:
    """Dispatches by engine. Does not call HTTP itself."""

    def __init__(
        self,
        *,
        google: SerpSnapshotProvider,
        yandex: SerpSnapshotProvider,
    ) -> None:
        self._google = google
        self._yandex = yandex

    def is_configured(self, engine: SearchEngine) -> bool:
        if engine == SearchEngine.GOOGLE:
            return self._google.is_configured(engine)
        if engine == SearchEngine.YANDEX:
            return self._yandex.is_configured(engine)
        return False

    async def snapshot(
        self,
        query: str,
        *,
        engine: SearchEngine,
        top_n: int = 20,
    ) -> SerpSnapshot:
        if engine == SearchEngine.GOOGLE:
            return await self._google.snapshot(query, engine=engine, top_n=top_n)
        if engine == SearchEngine.YANDEX:
            return await self._yandex.snapshot(query, engine=engine, top_n=top_n)
        raise DiscoveryConfigurationError(f"Unsupported search engine: {engine}")
