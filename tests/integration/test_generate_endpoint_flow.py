"""End-to-end flow: HTTP -> FastAPI -> ArticleService -> MockAIWriter -> PostgreSQL."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ai_writer
from app.core.exceptions import AIProviderError
from app.db.models.article import ArticleStatus
from app.services.ai.mock_writer import MockAIWriter

ENDPOINT = "/api/v1/articles/generate"


@pytest.mark.asyncio
async def test_generated_article_is_persisted(
    api_app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    api_app.dependency_overrides[get_ai_writer] = lambda: MockAIWriter()

    response = await client.post(
        ENDPOINT,
        json={
            "topic": "Как выбрать промышленный насос",
            "audience": "Инженеры и закупщики",
            "keywords": ["промышленный насос", "как выбрать насос"],
        },
    )

    assert response.status_code == 200
    body = response.json()

    row = (
        await db_session.execute(
            text(
                "SELECT status, title, word_count, keywords, language, audience, "
                "error_message FROM articles WHERE id = :id"
            ),
            {"id": uuid.UUID(body["id"])},
        )
    ).one()

    status, title, word_count, keywords, language, audience, error_message = row
    assert status == ArticleStatus.COMPLETED.value
    assert title == body["title"]
    assert word_count == body["word_count"]
    assert keywords == ["промышленный насос", "как выбрать насос"]
    assert language == "ru"
    assert audience == "Инженеры и закупщики"
    assert error_message is None


@pytest.mark.asyncio
async def test_failed_generation_is_persisted_as_failed(
    api_app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    writer = MockAIWriter(fail_with=AIProviderError())
    api_app.dependency_overrides[get_ai_writer] = lambda: writer

    response = await client.post(ENDPOINT, json={"topic": "Тема статьи"})

    assert response.status_code == 502
    article_id = uuid.UUID(response.json()["id"])

    row = (
        await db_session.execute(
            text(
                "SELECT status, error_message, content_markdown "
                "FROM articles WHERE id = :id"
            ),
            {"id": article_id},
        )
    ).one()

    status, error_message, content_markdown = row
    assert status == ArticleStatus.FAILED.value
    assert error_message == "Article generation failed due to an AI provider error"
    assert content_markdown is None
