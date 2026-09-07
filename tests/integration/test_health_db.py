"""Integration tests requiring a running PostgreSQL."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import get_engine


@pytest.mark.asyncio
async def test_database_accepts_select() -> None:
    engine = get_engine()
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_health_endpoint_against_real_database(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
