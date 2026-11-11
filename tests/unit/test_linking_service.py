"""Unit tests for LinkingService with an in-memory repository."""

import uuid
from typing import Any

import pytest

from app.db.models.article import Article, ArticleStatus
from app.services.linking_service import LinkingService


class FakeArticleRepository:
    def __init__(self, rows: list[Article] | None = None) -> None:
        self.rows = rows or []

    async def list_link_targets(self, **_kwargs: Any) -> list[Article]:
        return list(self.rows)


def _article(**overrides: Any) -> Article:
    payload: dict[str, Any] = {
        "id": uuid.uuid4(),
        "topic": "Как выбрать жесткость матраса",
        "language": "ru",
        "audience": "general",
        "keywords": ["жесткость матраса"],
        "title": "Как выбрать жесткость матраса",
        "url_slug": "kak-vybrat-zhestkost",
        "status": ArticleStatus.COMPLETED,
    }
    payload.update(overrides)
    return Article(**payload)


@pytest.mark.asyncio
async def test_inserts_link_to_completed_article() -> None:
    repo = FakeArticleRepository([_article()])
    service = LinkingService(repo, enabled=True, max_links=3, href_prefix="/")
    markdown = "Покупатели часто спрашивают про жесткость матраса зимой."

    updated, refs = await service.insert_links(
        markdown,
        article_id=uuid.uuid4(),
        language="ru",
        keywords=["жесткость матраса"],
        topic="Матрас",
    )

    assert refs
    assert "/kak-vybrat-zhestkost" in updated


@pytest.mark.asyncio
async def test_disabled_linking_is_noop() -> None:
    repo = FakeArticleRepository([_article()])
    service = LinkingService(repo, enabled=False)
    markdown = "жесткость матраса"

    updated, refs = await service.insert_links(
        markdown,
        article_id=uuid.uuid4(),
        language="ru",
        keywords=["жесткость матраса"],
        topic="Матрас",
    )

    assert updated == markdown
    assert refs == []
