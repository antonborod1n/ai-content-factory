"""Unit tests for ArticleService using in-memory doubles."""

import uuid
from typing import Any

import pytest

from app.core.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIValidationError,
    ArticleGenerationError,
    ArticleGenerationUpstreamError,
)
from app.core.word_count import count_words
from app.db.models.article import Article, ArticleStatus
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.services.ai.mock_writer import MockAIWriter
from app.services.article_service import ArticleService


class FakeArticleRepository:
    """In-memory stand-in for ArticleRepository."""

    def __init__(self) -> None:
        self.articles: dict[uuid.UUID, Article] = {}
        self.status_history: list[ArticleStatus] = []

    async def create(self, **fields: Any) -> Article:
        article = Article(id=uuid.uuid4(), **fields)
        self.articles[article.id] = article
        self.status_history.append(article.status)
        return article

    async def get_by_id(self, article_id: uuid.UUID) -> Article | None:
        return self.articles.get(article_id)

    async def update(self, article_id: uuid.UUID, **fields: Any) -> Article | None:
        article = self.articles.get(article_id)
        if article is None:
            return None
        for key, value in fields.items():
            setattr(article, key, value)
        if "status" in fields:
            self.status_history.append(fields["status"])
        return article


LEAKY_SECRET = "fake-password-must-not-leak"


class ExplodingWriter:
    """Writer that raises a non-AI error containing sensitive text."""

    async def generate(self, request: ArticleWriteInput) -> AIArticleOutput:
        raise RuntimeError(
            f"connection to postgresql://acf:{LEAKY_SECRET}@db failed"
        )


def _request(**overrides: Any) -> ArticleWriteInput:
    payload: dict[str, Any] = {
        "topic": "Как выбрать промышленный насос",
        "language": "ru",
        "audience": "Инженеры и закупщики",
        "keywords": ["промышленный насос"],
    }
    payload.update(overrides)
    return ArticleWriteInput(**payload)


@pytest.mark.asyncio
async def test_generate_completes_and_persists_content() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter()
    service = ArticleService(repository, writer)

    article = await service.generate(_request())

    assert article.status is ArticleStatus.COMPLETED
    assert article.title == "Mock: Как выбрать промышленный насос"
    assert article.meta_description
    assert article.content_markdown
    assert article.error_message is None
    assert article.word_count == count_words(article.content_markdown)


@pytest.mark.asyncio
async def test_generate_follows_status_transitions() -> None:
    repository = FakeArticleRepository()
    service = ArticleService(repository, MockAIWriter())

    await service.generate(_request())

    assert repository.status_history == [
        ArticleStatus.PENDING,
        ArticleStatus.PROCESSING,
        ArticleStatus.COMPLETED,
    ]


@pytest.mark.asyncio
async def test_generate_stores_request_parameters() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter()
    service = ArticleService(repository, writer)

    request = _request(language="en", audience="Buyers", keywords=["pump", "guide"])
    article = await service.generate(request)

    assert article.language == "en"
    assert article.audience == "Buyers"
    assert article.keywords == ["pump", "guide"]
    assert len(writer.calls) == 1
    assert writer.calls[0].topic == request.topic
    assert writer.calls[0].keywords == ["pump", "guide"]


@pytest.mark.asyncio
async def test_generate_recalculates_word_count_and_ignores_ai_value() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter(
        output=AIArticleOutput(
            title="Title",
            meta_description="Meta",
            content_markdown="# Heading\n\nexactly four real words",
            word_count=9999,
        )
    )
    service = ArticleService(repository, writer)

    article = await service.generate(_request())

    assert article.word_count == 5
    assert article.word_count != 9999


@pytest.mark.asyncio
async def test_generate_marks_failed_on_ai_provider_error() -> None:
    repository = FakeArticleRepository()
    service = ArticleService(repository, MockAIWriter(fail_with=AIProviderError()))

    with pytest.raises(ArticleGenerationUpstreamError) as exc_info:
        await service.generate(_request())

    article = next(iter(repository.articles.values()))
    assert exc_info.value.article_id == article.id
    assert isinstance(exc_info.value.__cause__, AIProviderError)
    assert article.status is ArticleStatus.FAILED
    assert article.error_message == (
        "Article generation failed due to an AI provider error"
    )
    assert article.content_markdown is None
    assert article.word_count is None
    assert repository.status_history == [
        ArticleStatus.PENDING,
        ArticleStatus.PROCESSING,
        ArticleStatus.FAILED,
    ]


@pytest.mark.asyncio
async def test_generate_marks_failed_on_invalid_ai_output() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter(invalid_payload={"title": "Only title"})
    service = ArticleService(repository, writer)

    with pytest.raises(ArticleGenerationUpstreamError) as exc_info:
        await service.generate(_request())

    article = next(iter(repository.articles.values()))
    assert isinstance(exc_info.value.__cause__, AIValidationError)
    assert article.status is ArticleStatus.FAILED
    assert article.error_message == "AI response failed validation"
    assert article.title is None


@pytest.mark.asyncio
async def test_generate_treats_misconfiguration_as_internal_error() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter(fail_with=AIConfigurationError())
    service = ArticleService(repository, writer)

    with pytest.raises(ArticleGenerationError) as exc_info:
        await service.generate(_request())

    assert not isinstance(exc_info.value, ArticleGenerationUpstreamError)
    assert str(exc_info.value) == "Article generation failed"

    article = next(iter(repository.articles.values()))
    assert article.status is ArticleStatus.FAILED
    assert article.error_message == "Article generation failed"


@pytest.mark.asyncio
async def test_generate_wraps_unexpected_error_with_safe_message() -> None:
    repository = FakeArticleRepository()
    service = ArticleService(repository, ExplodingWriter())

    with pytest.raises(ArticleGenerationError) as exc_info:
        await service.generate(_request())

    message = str(exc_info.value)
    assert message == "Article generation failed"
    assert LEAKY_SECRET not in message

    article = next(iter(repository.articles.values()))
    assert article.status is ArticleStatus.FAILED
    assert article.error_message == "Article generation failed"
    assert LEAKY_SECRET not in article.error_message
