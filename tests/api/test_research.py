"""API tests for competitor research."""

import uuid

import pytest
from httpx import AsyncClient

from app.db.models.research import ResearchStatus

RESEARCH = "/api/v1/research"


@pytest.mark.asyncio
async def test_create_research_returns_outline(client: AsyncClient) -> None:
    response = await client.post(
        RESEARCH,
        json={"topic": "Жесткий или мягкий матрас: какой лучше выбрать?"},
    )
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["status"] == ResearchStatus.COMPLETED.value
    assert len(body["outline"]) >= 2
    assert len(body["competitors"]) >= 1
    assert body["competitors"][0]["url"].startswith("https://example.com/")


@pytest.mark.asyncio
async def test_list_and_get_research(client: AsyncClient) -> None:
    created = await client.post(RESEARCH, json={"topic": "Как выбрать матрас"})
    research_id = created.json()["id"]

    listed = await client.get(RESEARCH)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    detail = await client.get(f"{RESEARCH}/{research_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == research_id


@pytest.mark.asyncio
async def test_get_research_404(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    response = await client.get(f"{RESEARCH}/{missing}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_research_rejects_blank_topic(client: AsyncClient) -> None:
    response = await client.post(RESEARCH, json={"topic": "  "})
    assert response.status_code == 422
