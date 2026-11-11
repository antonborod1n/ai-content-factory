"""Catalog/detail mapping for GET /articles."""

import uuid
from datetime import UTC, datetime

from app.db.models.article import Article, ArticleStatus
from app.schemas.articles import article_detail_response, article_list_item


def test_list_item_omits_markdown_and_fills_empty_title() -> None:
    now = datetime.now(UTC)
    article = Article(
        id=uuid.uuid4(),
        topic="Черновик",
        language="ru",
        status=ArticleStatus.PENDING,
        title=None,
        content_markdown="# Secret body",
        word_count=None,
        created_at=now,
        updated_at=now,
    )

    card = article_list_item(article)
    assert card.title == ""
    assert card.word_count == 0
    assert card.topic == "Черновик"
    assert "content_markdown" not in card.model_dump()


def test_detail_response_coerces_missing_body_fields() -> None:
    now = datetime.now(UTC)
    article = Article(
        id=uuid.uuid4(),
        topic="Черновик",
        language="ru",
        status=ArticleStatus.FAILED,
        title=None,
        meta_description=None,
        content_markdown=None,
        word_count=None,
        created_at=now,
        updated_at=now,
    )

    detail = article_detail_response(article)
    assert detail.title == ""
    assert detail.meta_description == ""
    assert detail.content_markdown == ""
    assert detail.word_count == 0
    assert detail.status is ArticleStatus.FAILED
