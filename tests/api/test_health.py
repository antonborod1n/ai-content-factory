"""API tests for GET /health."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_database_health


@pytest.mark.asyncio
async def test_health_ok_when_database_available(
    api_app: FastAPI, client: AsyncClient
) -> None:
    api_app.dependency_overrides[get_database_health] = lambda: True

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.asyncio
async def test_health_degraded_when_database_unavailable(
    api_app: FastAPI, client: AsyncClient
) -> None:
    api_app.dependency_overrides[get_database_health] = lambda: False

    response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "error"}
