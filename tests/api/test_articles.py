"""API tests for POST /api/v1/articles/generate."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_ai_writer
from app.core.exceptions import AIProviderError
from app.core.word_count import count_words
from app.db.models.article import ArticleStatus
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.services.ai.mock_writer import MockAIWriter

ENDPOINT = "/api/v1/articles/generate"


LEAKY_SECRET = "fake-password-must-not-leak"


class ExplodingWriter:
    """Writer raising a non-AI error with sensitive text."""

    async def generate(self, request: ArticleWriteInput) -> AIArticleOutput:
        raise RuntimeError(f"postgresql://acf:{LEAKY_SECRET}@db/acf unreachable")


def _use_writer(api_app: FastAPI, writer: object) -> None:
    api_app.dependency_overrides[get_ai_writer] = lambda: writer


@pytest.mark.asyncio
async def test_generate_returns_completed_article(
    api_app: FastAPI, client: AsyncClient
) -> None:
    _use_writer(api_app, MockAIWriter())

    response = await client.post(
        ENDPOINT,
        json={
            "topic": "Как выбрать промышленный насос",
            "language": "ru",
            "audience": "Инженеры и закупщики",
            "keywords": ["промышленный насос"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "status",
        "title",
        "meta_description",
        "content_markdown",
        "word_count",
    }
    uuid.UUID(body["id"])
    assert body["status"] == ArticleStatus.COMPLETED.value
    assert body["title"] == "Mock: Как выбрать промышленный насос"
    assert body["word_count"] == count_words(body["content_markdown"])


@pytest.mark.asyncio
async def test_generate_applies_defaults(
    api_app: FastAPI, client: AsyncClient
) -> None:
    writer = MockAIWriter()
    _use_writer(api_app, writer)

    response = await client.post(ENDPOINT, json={"topic": "Only topic"})

    assert response.status_code == 200
    assert len(writer.calls) == 1
    call = writer.calls[0]
    assert call.language == "ru"
    assert call.audience == "general"
    assert call.keywords == []


@pytest.mark.asyncio
async def test_generate_requires_topic(
    api_app: FastAPI, client: AsyncClient
) -> None:
    _use_writer(api_app, MockAIWriter())

    response = await client.post(ENDPOINT, json={"language": "ru"})

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("topic", ["", "   ", "\n\t"])
async def test_generate_rejects_blank_topic(
    api_app: FastAPI, client: AsyncClient, topic: str
) -> None:
    _use_writer(api_app, MockAIWriter())

    response = await client.post(ENDPOINT, json={"topic": topic})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_returns_502_on_ai_error(
    api_app: FastAPI, client: AsyncClient
) -> None:
    _use_writer(api_app, MockAIWriter(fail_with=AIProviderError()))

    response = await client.post(ENDPOINT, json={"topic": "Topic"})

    assert response.status_code == 502
    body = response.json()
    assert body["detail"] == (
        "Article generation failed due to an AI provider error"
    )
    assert body["status"] == ArticleStatus.FAILED.value
    uuid.UUID(body["id"])


@pytest.mark.asyncio
async def test_generate_returns_502_on_invalid_ai_response(
    api_app: FastAPI, client: AsyncClient
) -> None:
    _use_writer(api_app, MockAIWriter(invalid_payload={"title": "Only title"}))

    response = await client.post(ENDPOINT, json={"topic": "Topic"})

    assert response.status_code == 502
    assert response.json()["detail"] == "AI response failed validation"


@pytest.mark.asyncio
async def test_generate_returns_500_and_hides_internal_details(
    api_app: FastAPI, client: AsyncClient
) -> None:
    _use_writer(api_app, ExplodingWriter())

    response = await client.post(ENDPOINT, json={"topic": "Topic"})

    assert response.status_code == 500
    raw_body = response.text
    assert LEAKY_SECRET not in raw_body
    assert "Traceback" not in raw_body
    assert response.json()["detail"] == "Article generation failed"
