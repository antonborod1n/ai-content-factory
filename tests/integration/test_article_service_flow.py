"""Integration tests: ArticleService -> MockAIWriter -> PostgreSQL."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AIProviderError, ArticleGenerationUpstreamError
from app.core.word_count import count_words
from app.db.models.article import ArticleStatus
from app.repositories.article_repository import ArticleRepository
from app.schemas.ai import ArticleWriteInput
from app.services.ai.mock_writer import MockAIWriter
from app.services.article_service import ArticleService


def _request() -> ArticleWriteInput:
    return ArticleWriteInput(
        topic="Как выбрать промышленный насос",
        language="ru",
        audience="Инженеры и закупщики",
        keywords=["промышленный насос", "как выбрать насос"],
    )


@pytest.mark.asyncio
async def test_completed_article_is_stored_in_postgres(
    article_repository: ArticleRepository,
    db_session: AsyncSession,
) -> None:
    service = ArticleService(article_repository, MockAIWriter())

    article = await service.generate(_request())

    row = (
        await db_session.execute(
            text(
                "SELECT status, word_count, title, keywords, error_message "
                "FROM articles WHERE id = :id"
            ),
            {"id": article.id},
        )
    ).one()

    status, word_count, title, keywords, error_message = row
    assert status == ArticleStatus.COMPLETED.value
    assert word_count == count_words(article.content_markdown)
    assert word_count > 0
    assert title == article.title
    assert keywords == ["промышленный насос", "как выбрать насос"]
    assert error_message is None


@pytest.mark.asyncio
async def test_failed_article_is_stored_with_safe_message(
    article_repository: ArticleRepository,
    db_session: AsyncSession,
) -> None:
    writer = MockAIWriter(fail_with=AIProviderError())
    service = ArticleService(article_repository, writer)

    with pytest.raises(ArticleGenerationUpstreamError):
        await service.generate(_request())

    row = (
        await db_session.execute(
            text(
                "SELECT status, error_message, content_markdown, word_count "
                "FROM articles"
            )
        )
    ).one()

    status, error_message, content_markdown, word_count = row
    assert status == ArticleStatus.FAILED.value
    assert error_message == "Article generation failed due to an AI provider error"
    assert content_markdown is None
    assert word_count is None


@pytest.mark.asyncio
async def test_repository_can_read_back_generated_article(
    article_repository: ArticleRepository,
) -> None:
    service = ArticleService(article_repository, MockAIWriter())

    article = await service.generate(_request())
    found = await article_repository.get_by_id(article.id)

    assert found is not None
    assert found.id == article.id
    assert found.status is ArticleStatus.COMPLETED
    assert found.content_markdown == article.content_markdown
