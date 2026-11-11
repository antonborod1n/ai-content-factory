"""Integration: ingest → vector search → generate with RAG context."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ai_writer
from app.db.models.document import DocumentStatus
from app.services.ai.mock_writer import MockAIWriter


@pytest.mark.asyncio
async def test_generate_uses_ingested_knowledge(
    api_app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    writer = MockAIWriter()
    api_app.dependency_overrides[get_ai_writer] = lambda: writer

    ingest = await client.post(
        "/api/v1/documents",
        json={
            "title": "Спека насоса ACME",
            "content": (
                "Насос ACME-100 рассчитан на напор 40 метров и подачу 12 м3/ч. "
                "Не используйте его с агрессивными кислотами."
            ),
        },
    )
    assert ingest.status_code == 201
    assert ingest.json()["status"] == DocumentStatus.READY.value

    response = await client.post(
        "/api/v1/articles/generate",
        json={
            "topic": "Как подобрать насос ACME-100 по напору",
            "keywords": ["ACME-100", "напор"],
        },
    )
    assert response.status_code == 200
    assert writer.calls
    context = writer.calls[0].knowledge_context
    assert "ACME-100" in context
    assert "40 метров" in context


@pytest.mark.asyncio
async def test_generate_without_kb_has_empty_context(
    api_app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    writer = MockAIWriter()
    api_app.dependency_overrides[get_ai_writer] = lambda: writer

    response = await client.post(
        "/api/v1/articles/generate",
        json={"topic": "Как выбрать промышленный насос"},
    )
    assert response.status_code == 200
    assert writer.calls[0].knowledge_context == ""
