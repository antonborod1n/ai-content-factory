"""Integration: Stage 5 images and internal links persist in PostgreSQL."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ai_writer
from app.db.models.article import ArticleStatus
from app.schemas.ai import AIArticleOutput
from app.services.ai.mock_writer import MockAIWriter

ENDPOINT = "/api/v1/articles/generate"


@pytest.mark.asyncio
async def test_image_assets_are_persisted_without_bytes(
    api_app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    writer = MockAIWriter(
        output=AIArticleOutput(
            title="Матрас",
            meta_description="Meta",
            url_slug="matras",
            content_markdown="# Матрас\n\n![Кадр](IMAGE_PLACEHOLDER_1)\n",
            word_count=3,
        )
    )
    api_app.dependency_overrides[get_ai_writer] = lambda: writer

    response = await client.post(
        ENDPOINT,
        json={"topic": "Матрас", "use_images": True, "use_internal_links": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert "images/cover.png" in body["content_markdown"]
    assert "images/image-1.png" in body["content_markdown"]
    assert "data" not in body["assets"][0]

    row = (
        await db_session.execute(
            text("SELECT status, assets FROM articles WHERE id = :id"),
            {"id": uuid.UUID(body["id"])},
        )
    ).one()
    status, assets = row
    assert status == ArticleStatus.COMPLETED.value
    paths = {item["path"] for item in assets}
    assert paths == {"images/cover.png", "images/image-1.png"}
    assert all(item["status"] == "completed" for item in assets)
    assert "data" not in assets[0]


@pytest.mark.asyncio
async def test_second_generate_persists_internal_links(
    api_app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    first = MockAIWriter(
        output=AIArticleOutput(
            title="Как выбрать жесткость матраса",
            meta_description="Meta",
            url_slug="kak-vybrat-zhestkost",
            content_markdown="# Как выбрать жесткость матраса\n\nБазовый гид.",
            word_count=5,
        )
    )
    api_app.dependency_overrides[get_ai_writer] = lambda: first
    first_response = await client.post(
        ENDPOINT,
        json={
            "topic": "Как выбрать жесткость матраса",
            "keywords": ["жесткость матраса"],
            "use_internal_links": False,
        },
    )
    assert first_response.status_code == 200

    second = MockAIWriter(
        output=AIArticleOutput(
            title="Вес и поза сна",
            meta_description="Meta",
            url_slug="ves-i-poza",
            content_markdown=(
                "# Вес\n\nПри выборе смотрите на жесткость матраса и вес."
            ),
            word_count=8,
        )
    )
    api_app.dependency_overrides[get_ai_writer] = lambda: second
    response = await client.post(
        ENDPOINT,
        json={
            "topic": "Вес и поза сна",
            "keywords": ["жесткость матраса"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "/kak-vybrat-zhestkost" in body["content_markdown"]

    row = (
        await db_session.execute(
            text("SELECT internal_links FROM articles WHERE id = :id"),
            {"id": uuid.UUID(body["id"])},
        )
    ).one()
    (internal_links,) = row
    assert internal_links[0]["url_slug"] == "kak-vybrat-zhestkost"
