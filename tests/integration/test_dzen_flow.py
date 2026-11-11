"""Integration: Dzen version persists on the article row."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ai_writer
from app.db.models.article import ArticleStatus
from app.services.ai.mock_writer import MockAIWriter

ENDPOINT = "/api/v1/articles/generate"


@pytest.mark.asyncio
async def test_dzen_payload_is_persisted(
    api_app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    api_app.dependency_overrides[get_ai_writer] = lambda: MockAIWriter()

    response = await client.post(
        ENDPOINT,
        json={"topic": "Как выбрать матрас", "use_dzen": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dzen"]["status"] == "completed"
    assert "DZEN_COVER_PLACEHOLDER" in body["dzen"]["content_markdown"]

    row = (
        await db_session.execute(
            text("SELECT status, dzen FROM articles WHERE id = :id"),
            {"id": uuid.UUID(body["id"])},
        )
    ).one()
    status, dzen = row
    assert status == ArticleStatus.COMPLETED.value
    assert dzen["title"]
    assert dzen["char_count"] == len(dzen["content_markdown"])
    assert "data" not in (dzen.get("assets") or [{}])[0]
