"""Integration: multi-agent generate persists editor output and pipeline JSON."""

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
async def test_multi_agent_generate_is_persisted(
    api_app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    api_app.dependency_overrides[get_ai_writer] = lambda: MockAIWriter()

    response = await client.post(
        ENDPOINT,
        json={"topic": "Жесткость матраса", "use_multi_agent": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"].startswith("Edited: ")
    assert body["pipeline"]["enabled"] is True

    row = (
        await db_session.execute(
            text(
                "SELECT status, title, pipeline FROM articles WHERE id = :id"
            ),
            {"id": uuid.UUID(body["id"])},
        )
    ).one()
    status, title, pipeline = row
    assert status == ArticleStatus.COMPLETED.value
    assert title == body["title"]
    assert pipeline["steps"][-1]["name"] == "editor"
    assert pipeline["steps"][-2]["name"] == "fact_checker"
    assert pipeline["steps"][-2]["verdict"] == "ok"
