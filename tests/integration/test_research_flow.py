"""Integration: research → generate uses competitor outline."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_ai_writer
from app.services.ai.mock_writer import MockAIWriter


@pytest.mark.asyncio
async def test_generate_with_competitor_research_uses_outline(
    api_app: FastAPI,
    client: AsyncClient,
) -> None:
    writer = MockAIWriter()
    api_app.dependency_overrides[get_ai_writer] = lambda: writer

    research = await client.post(
        "/api/v1/research",
        json={"topic": "Жесткий или мягкий матрас"},
    )
    assert research.status_code == 201
    research_id = research.json()["id"]
    outline = research.json()["outline"]

    response = await client.post(
        "/api/v1/articles/generate",
        json={
            "topic": "Жесткий или мягкий матрас",
            "research_id": research_id,
            "outline": ["Этот план должен быть заменён"],
        },
    )
    assert response.status_code == 200
    assert writer.calls
    used = writer.calls[0]
    assert used.outline == outline
    assert used.word_count is not None
    assert used.competitor_context
    assert "example.com" in used.competitor_context
    sources = response.json()["competitor_sources"]
    assert sources
    assert all(item["url"].startswith("https://example.com/") for item in sources)


@pytest.mark.asyncio
async def test_generate_inline_research_flag(
    api_app: FastAPI,
    client: AsyncClient,
) -> None:
    writer = MockAIWriter()
    api_app.dependency_overrides[get_ai_writer] = lambda: writer

    response = await client.post(
        "/api/v1/articles/generate",
        json={
            "topic": "Жесткий или мягкий матрас",
            "use_competitor_research": True,
        },
    )
    assert response.status_code == 200
    assert writer.calls[0].outline
    assert writer.calls[0].competitor_context
    assert response.json()["competitor_sources"]
