"""API tests for GET /health."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok_when_database_available(client: AsyncClient) -> None:
    with patch(
        "app.api.routes.health.check_database_connection",
        new=AsyncMock(return_value=True),
    ):
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.asyncio
async def test_health_degraded_when_database_unavailable(client: AsyncClient) -> None:
    with patch(
        "app.api.routes.health.check_database_connection",
        new=AsyncMock(return_value=False),
    ):
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "error"}
