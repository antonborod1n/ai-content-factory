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
        "url_slug",
        "content_markdown",
        "word_count",
        "pipeline",
        "assets",
        "internal_links",
        "dzen",
        "quality",
        "competitor_sources",
        "review_status",
    }
    uuid.UUID(body["id"])
    assert body["status"] == ArticleStatus.COMPLETED.value
    assert body["title"] == "Mock: Как выбрать промышленный насос"
    assert body["word_count"] == count_words(body["content_markdown"])
    assert body["pipeline"] is None
    assert body["assets"] is None
    assert body["internal_links"] == []
    assert body["dzen"] is None
    assert body["quality"] is None
    assert body["competitor_sources"] is None
    assert body["review_status"] == "pending"


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
    assert call.use_text is True
    assert call.use_images is False
    assert call.use_internal_links is True
    assert call.use_dzen is False
    assert call.use_detectors is False
    assert call.use_humanizer is False
    assert call.use_summary is False


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


@pytest.mark.asyncio
async def test_generate_multi_agent_returns_pipeline_trace(
    api_app: FastAPI, client: AsyncClient
) -> None:
    writer = MockAIWriter()
    _use_writer(api_app, writer)

    response = await client.post(
        ENDPOINT,
        json={"topic": "Жесткость матраса", "use_multi_agent": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"].startswith("Edited: ")
    assert body["pipeline"] is not None
    names = [step["name"] for step in body["pipeline"]["steps"]]
    assert names == ["research", "seo", "writer", "fact_checker", "editor"]
    assert writer.calls
    assert writer.calls[0].outline


@pytest.mark.asyncio
async def test_generate_replaces_image_placeholders(
    api_app: FastAPI, client: AsyncClient
) -> None:
    writer = MockAIWriter(
        output=AIArticleOutput(
            title="Матрас",
            meta_description="Meta",
            url_slug="matras",
            content_markdown=(
                "# Матрас\n\nТекст.\n\n![Кадр](IMAGE_PLACEHOLDER_1)\n"
            ),
            word_count=3,
        )
    )
    _use_writer(api_app, writer)

    response = await client.post(
        ENDPOINT,
        json={"topic": "Матрас", "use_images": True, "use_internal_links": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert "images/cover.png" in body["content_markdown"]
    assert "images/image-1.png" in body["content_markdown"]
    assert {item["kind"] for item in body["assets"]} == {"hero", "image"}
    assert all(item["status"] == "completed" for item in body["assets"])
    assert "data" not in body["assets"][0]
    assert body["internal_links"] is None


@pytest.mark.asyncio
async def test_generate_inserts_internal_link(
    api_app: FastAPI, client: AsyncClient
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
    _use_writer(api_app, first)
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
    _use_writer(api_app, second)
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
    assert body["internal_links"]
    assert body["internal_links"][0]["url_slug"] == "kak-vybrat-zhestkost"


@pytest.mark.asyncio
async def test_generate_dzen_returns_short_version(
    api_app: FastAPI, client: AsyncClient
) -> None:
    _use_writer(api_app, MockAIWriter())

    response = await client.post(
        ENDPOINT,
        json={"topic": "Как выбрать матрас", "use_dzen": True, "use_images": True},
    )
    assert response.status_code == 200
    body = response.json()
    dzen = body["dzen"]
    assert dzen["status"] == "completed"
    assert dzen["title"]
    assert "images/dzen-cover.png" in dzen["content_markdown"]
    assert "images/dzen-1.png" in dzen["content_markdown"]
    assert "images/dzen-2.png" in dzen["content_markdown"]
    assert "data" not in dzen["assets"][0]
    assert dzen["char_count"] == len(dzen["content_markdown"])


@pytest.mark.asyncio
async def test_generate_quality_returns_scores(
    api_app: FastAPI, client: AsyncClient
) -> None:
    _use_writer(api_app, MockAIWriter())

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
    assert quality["detectors"]["ai_likelihood"] == 32
    assert quality["detectors"]["uniqueness"] == 78
    assert quality["detectors"]["verdict"] == "pass"
    assert quality["humanizer"]["applied"] is True
    assert "естественнее" in body["content_markdown"]
    assert quality["summary"]["text"].startswith("Кратко:")
    assert "content_markdown" not in quality


@pytest.mark.asyncio
async def test_generate_rejects_neither_text_nor_images(
    api_app: FastAPI, client: AsyncClient
) -> None:
    _use_writer(api_app, MockAIWriter())
    response = await client.post(
        ENDPOINT,
        json={"topic": "Матрас", "use_text": False, "use_images": False},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_regenerate_images_keeps_text(
    api_app: FastAPI, client: AsyncClient
) -> None:
    writer = MockAIWriter(
        output=AIArticleOutput(
            title="Матрас",
            meta_description="Meta",
            url_slug="matras",
            content_markdown="# Матрас\n\n![Кадр](IMAGE_PLACEHOLDER_1)\n",
            word_count=2,
        )
    )
    _use_writer(api_app, writer)
    created = await client.post(
        ENDPOINT,
        json={"topic": "Матрас", "use_images": False, "use_internal_links": False},
    )
    assert created.status_code == 200
    article_id = created.json()["id"]
    body_before = created.json()["content_markdown"]

    writer.calls.clear()
    response = await client.post(f"/api/v1/articles/{article_id}/images")
    assert response.status_code == 200
    body = response.json()
    assert writer.calls == []
    assert body["id"] == article_id
    assert "images/cover.png" in body["content_markdown"]
    assert "images/image-1.png" in body["content_markdown"]
    assert body["title"] == "Матрас"
    assert "IMAGE_PLACEHOLDER_1" in body_before
    assert "IMAGE_PLACEHOLDER_1" not in body["content_markdown"]


@pytest.mark.asyncio
async def test_list_and_get_article(
    api_app: FastAPI, client: AsyncClient
) -> None:
    _use_writer(api_app, MockAIWriter())
    created = await client.post(
        ENDPOINT,
        json={"topic": "Как выбрать промышленный насос"},
    )
    assert created.status_code == 200
    article_id = created.json()["id"]
    markdown = created.json()["content_markdown"]

    listed = await client.get("/api/v1/articles")
    assert listed.status_code == 200
    catalog = listed.json()
    assert catalog["total"] == 1
    card = catalog["items"][0]
    assert card["id"] == article_id
    assert card["topic"] == "Как выбрать промышленный насос"
    assert card["status"] == ArticleStatus.COMPLETED.value
    assert "content_markdown" not in card

    filtered = await client.get(
        "/api/v1/articles",
        params={"status": ArticleStatus.COMPLETED.value},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    empty = await client.get(
        "/api/v1/articles",
        params={"status": ArticleStatus.FAILED.value},
    )
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "total": 0}

    detail = await client.get(f"/api/v1/articles/{article_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == article_id
    assert body["content_markdown"] == markdown
    assert body["title"] == created.json()["title"]


@pytest.mark.asyncio
async def test_get_article_returns_404(client: AsyncClient) -> None:
    missing = await client.get(f"/api/v1/articles/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Article not found"


@pytest.mark.asyncio
async def test_review_article(api_app: FastAPI, client: AsyncClient) -> None:
    _use_writer(api_app, MockAIWriter())
    created = await client.post(ENDPOINT, json={"topic": "Ревью"})
    article_id = created.json()["id"]

    approved = await client.patch(
        f"/api/v1/articles/{article_id}/review",
        json={"review_status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"
    assert approved.json()["content_markdown"] == created.json()["content_markdown"]

    listed = await client.get(
        "/api/v1/articles",
        params={"review_status": "approved"},
    )
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["review_status"] == "approved"

    missing = await client.patch(
        f"/api/v1/articles/{uuid.uuid4()}/review",
        json={"review_status": "rejected"},
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_cors_allows_vite_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/articles",
        headers={
            "Origin": "http://localhost:15173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:15173"
    )
