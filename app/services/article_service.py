"""Article generation orchestration."""

from __future__ import annotations

import logging
import uuid

from app.core.exceptions import AIError, ArticleGenerationError
from app.core.word_count import count_words
from app.db.models.article import Article, ArticleStatus
from app.repositories.article_repository import ArticleRepository
from app.schemas.ai import ArticleWriteInput
from app.services.ai.base import AIWriter

logger = logging.getLogger(__name__)

_GENERIC_FAILURE_MESSAGE = "Article generation failed"


class ArticleService:
    """Owns the Stage 1 generation flow and article status transitions."""

    def __init__(self, repository: ArticleRepository, writer: AIWriter) -> None:
        self._repository = repository
        self._writer = writer

    async def generate(self, request: ArticleWriteInput) -> Article:
        """Generate an article and persist it.

        Flow: pending -> processing -> AI call -> validated output ->
        recalculated word_count -> completed. Any failure stores a safe
        error message and leaves the article in the failed state.
        """
        article = await self._repository.create(
            topic=request.topic,
            language=request.language,
            audience=request.audience,
            keywords=list(request.keywords),
            status=ArticleStatus.PENDING,
        )
        await self._repository.update(article.id, status=ArticleStatus.PROCESSING)

        try:
            output = await self._writer.generate(request)
        except AIError as exc:
            await self._mark_failed(article.id, exc.message)
            raise
        except Exception as exc:
            logger.exception("Unexpected error while generating article")
            await self._mark_failed(article.id, _GENERIC_FAILURE_MESSAGE)
            raise ArticleGenerationError(_GENERIC_FAILURE_MESSAGE) from exc

        completed = await self._repository.update(
            article.id,
            title=output.title,
            meta_description=output.meta_description,
            content_markdown=output.content_markdown,
            word_count=count_words(output.content_markdown),
            status=ArticleStatus.COMPLETED,
            error_message=None,
        )
        if completed is None:
            raise ArticleGenerationError(_GENERIC_FAILURE_MESSAGE)
        return completed

    async def _mark_failed(self, article_id: uuid.UUID, message: str) -> None:
        try:
            await self._repository.update(
                article_id,
                status=ArticleStatus.FAILED,
                error_message=message,
            )
        except Exception:
            # Never mask the original failure with a bookkeeping error.
            logger.exception("Could not mark article %s as failed", article_id)
