"""Tests for ArticleRepository (PostgreSQL, no OpenAI)."""

import uuid

import pytest

from app.db.models.article import ArticleStatus
from app.repositories.article_repository import ArticleRepository


@pytest.mark.asyncio
async def test_create_article_with_defaults(
    article_repository: ArticleRepository,
) -> None:
    article = await article_repository.create(topic="Industrial pumps")

    assert isinstance(article.id, uuid.UUID)
    assert article.topic == "Industrial pumps"
    assert article.language == "ru"
    assert article.audience == "general"
    assert article.keywords == []
    assert article.status is ArticleStatus.PENDING
    assert article.title is None
    assert article.created_at is not None
    assert article.updated_at is not None


@pytest.mark.asyncio
async def test_create_article_with_explicit_fields(
    article_repository: ArticleRepository,
) -> None:
    article = await article_repository.create(
        topic="Pump selection",
        language="en",
        audience="Engineers",
        keywords=["pump", "selection"],
        status=ArticleStatus.PROCESSING,
    )

    assert article.language == "en"
    assert article.audience == "Engineers"
    assert article.keywords == ["pump", "selection"]
    assert article.status is ArticleStatus.PROCESSING


@pytest.mark.asyncio
async def test_get_by_id_returns_article(
    article_repository: ArticleRepository,
) -> None:
    created = await article_repository.create(topic="Lookup test")
    found = await article_repository.get_by_id(created.id)

    assert found is not None
    assert found.id == created.id
    assert found.topic == "Lookup test"


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_missing(
    article_repository: ArticleRepository,
) -> None:
    found = await article_repository.get_by_id(uuid.uuid4())
    assert found is None


@pytest.mark.asyncio
async def test_update_article_fields(
    article_repository: ArticleRepository,
) -> None:
    created = await article_repository.create(topic="Draft")
    updated = await article_repository.update(
        created.id,
        status=ArticleStatus.COMPLETED,
        title="Final title",
        meta_description="Meta",
        content_markdown="# Hello",
        word_count=1,
    )

    assert updated is not None
    assert updated.status is ArticleStatus.COMPLETED
    assert updated.title == "Final title"
    assert updated.meta_description == "Meta"
    assert updated.content_markdown == "# Hello"
    assert updated.word_count == 1


@pytest.mark.asyncio
async def test_update_missing_article_returns_none(
    article_repository: ArticleRepository,
) -> None:
    updated = await article_repository.update(
        uuid.uuid4(),
        status=ArticleStatus.FAILED,
        error_message="safe error",
    )
    assert updated is None


@pytest.mark.asyncio
async def test_update_rejects_unknown_field(
    article_repository: ArticleRepository,
) -> None:
    created = await article_repository.create(topic="Draft")
    with pytest.raises(ValueError, match="Unknown article field"):
        await article_repository.update(created.id, not_a_column="x")


@pytest.mark.asyncio
async def test_list_articles_ordered_and_filterable(
    article_repository: ArticleRepository,
) -> None:
    first = await article_repository.create(topic="First")
    second = await article_repository.create(
        topic="Second",
        status=ArticleStatus.FAILED,
        error_message="safe",
    )
    await article_repository.create(topic="Third")

    all_articles = await article_repository.list()
    assert len(all_articles) == 3
    assert all_articles[0].created_at >= all_articles[1].created_at
    assert {item.topic for item in all_articles} == {"First", "Second", "Third"}

    failed = await article_repository.list(status=ArticleStatus.FAILED)
    assert len(failed) == 1
    assert failed[0].id == second.id

    limited = await article_repository.list(limit=1, offset=0)
    assert len(limited) == 1

    offset_page = await article_repository.list(limit=1, offset=1)
    assert len(offset_page) == 1
    assert offset_page[0].id != limited[0].id
    assert first.id in {all_articles[0].id, all_articles[1].id, all_articles[2].id}

    assert await article_repository.count() == 3
    assert await article_repository.count(status=ArticleStatus.FAILED) == 1


@pytest.mark.asyncio
async def test_list_link_targets_returns_completed_with_slug(
    article_repository: ArticleRepository,
) -> None:
    usable = await article_repository.create(topic="Usable")
    usable = await article_repository.update(
        usable.id,
        status=ArticleStatus.COMPLETED,
        title="Как выбрать жесткость",
        url_slug="kak-vybrat-zhestkost",
        language="ru",
    )
    pending = await article_repository.create(topic="Pending")
    other_lang = await article_repository.create(topic="English", language="en")
    await article_repository.update(
        other_lang.id,
        status=ArticleStatus.COMPLETED,
        title="Firmness",
        url_slug="firmness",
    )
    empty_slug = await article_repository.create(topic="Empty slug")
    await article_repository.update(
        empty_slug.id,
        status=ArticleStatus.COMPLETED,
        title="No slug",
        url_slug="",
    )

    rows = await article_repository.list_link_targets(
        language="ru",
        exclude_id=pending.id,
    )
    assert [item.id for item in rows] == [usable.id]
