"""Integration: quality payload persists on the article row."""

import json
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
async def test_quality_payload_is_persisted(
    api_app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    api_app.dependency_overrides[get_ai_writer] = lambda: MockAIWriter()

    response = await client.post(
        ENDPOINT,
        json={
            "topic": "Как выбрать матрас",
            "use_detectors": True,
            "use_humanizer": True,
            "use_summary": True,
            "use_internal_links": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    quality = body["quality"]
    assert quality["detectors"]["status"] == "completed"
    assert quality["humanizer"]["applied"] is True
    assert quality["summary"]["text"]
    dumped = json.dumps(quality)
    assert "content_markdown" not in dumped
    assert "IMAGE_PLACEHOLDER" not in dumped

    row = (
        await db_session.execute(
            text(
                "SELECT status, quality, content_markdown "
                "FROM articles WHERE id = :id"
            ),
            {"id": uuid.UUID(body["id"])},
        )
    ).one()
    status, stored, markdown = row
    assert status == ArticleStatus.COMPLETED.value
    assert stored["detectors"]["verdict"] == "pass"
    assert stored["detectors"]["ai_likelihood"] == 32
    assert "естественнее" in markdown
    assert "content_markdown" not in json.dumps(stored)
    assert stored["summary"]["text"].startswith("Кратко:")
