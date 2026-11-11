"""RoutingSerpSnapshotProvider dispatches by engine."""

import pytest

from app.core.exceptions import DiscoveryConfigurationError
from app.schemas.discovery import SearchEngine
from app.services.discovery.mock_snapshotter import MockSerpSnapshotProvider
from app.services.discovery.routing import RoutingSerpSnapshotProvider


@pytest.mark.asyncio
async def test_routing_dispatches_and_reports_config() -> None:
    google = MockSerpSnapshotProvider(configured={SearchEngine.GOOGLE})
    yandex = MockSerpSnapshotProvider(configured=set())
    router = RoutingSerpSnapshotProvider(google=google, yandex=yandex)
    assert router.is_configured(SearchEngine.GOOGLE) is True
    assert router.is_configured(SearchEngine.YANDEX) is False
    snapshot = await router.snapshot(
        "матрас", engine=SearchEngine.GOOGLE, top_n=3
    )
    assert snapshot.engine == SearchEngine.GOOGLE
    assert google.calls
    assert not yandex.calls


@pytest.mark.asyncio
async def test_routing_rejects_unknown_engine() -> None:
    router = RoutingSerpSnapshotProvider(
        google=MockSerpSnapshotProvider(),
        yandex=MockSerpSnapshotProvider(),
    )
    with pytest.raises(DiscoveryConfigurationError):
        await router.snapshot("q", engine="bing")  # type: ignore[arg-type]
