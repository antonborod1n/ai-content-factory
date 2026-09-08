"""Article generation orchestration."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.config import get_settings
from app.core.article_file import try_save_article_to_file
from app.core.exceptions import (
    AIConfigurationError,
    AIError,
    ArticleGenerationError,
    ArticleGenerationUpstreamError,
)
from app.core.url_slug import normalize_url_slug
from app.core.word_count import count_words
from app.db.models.article import Article, ArticleStatus
from app.repositories.article_repository import ArticleRepository
from app.schemas.ai import ArticleWriteInput
from app.services.ai.base import AIWriter

logger = logging.getLogger(__name__)

_GENERIC_FAILURE_MESSAGE = "Article generation failed"


class ArticleService:
    """Owns the Stage 1 generation flow and article status transitions."""

    def __init__(
        self,
        repository: ArticleRepository,
        writer: AIWriter,
        *,
        output_dir: Path | str | None = None,
    ) -> None:
        self._repository = repository
        self._writer = writer
        if output_dir is None:
            self._output_dir: Path | str | None = (
                get_settings().articles_output_dir
            )
        else:
            self._output_dir = output_dir

    async def generate(self, request: ArticleWriteInput) -> Article:
        """Generate an article and persist it.

        Flow: pending -> processing -> AI call -> validated output ->
        recalculated word_count -> completed (+ optional Markdown file).
        Any failure stores a safe error message and leaves the article failed.
        """
        article = await self._repository.create(
            topic=request.topic,
            language=request.language,
            audience=request.audience,
            keywords=request.keywords_for_storage(),
            status=ArticleStatus.PENDING,
        )
        await self._repository.update(article.id, status=ArticleStatus.PROCESSING)

        try:
            output = await self._writer.generate(request)
        except AIConfigurationError as exc:
            logger.exception("AI provider is not configured")
            await self._mark_failed(article.id, _GENERIC_FAILURE_MESSAGE)
            raise ArticleGenerationError(
                _GENERIC_FAILURE_MESSAGE,
                article_id=article.id,
            ) from exc
        except AIError as exc:
            await self._mark_failed(article.id, exc.message)
            raise ArticleGenerationUpstreamError(
                exc.message,
                article_id=article.id,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error while generating article")
            await self._mark_failed(article.id, _GENERIC_FAILURE_MESSAGE)
            raise ArticleGenerationError(
                _GENERIC_FAILURE_MESSAGE,
                article_id=article.id,
            ) from exc

        completed = await self._repository.update(
            article.id,
            title=output.title,
            meta_description=output.meta_description,
            url_slug=normalize_url_slug(output.url_slug, article_id=article.id),
            content_markdown=output.content_markdown,
            word_count=count_words(output.content_markdown),
            status=ArticleStatus.COMPLETED,
            error_message=None,
        )
        if completed is None:
            raise ArticleGenerationError(
                _GENERIC_FAILURE_MESSAGE,
                article_id=article.id,
            )
        try_save_article_to_file(completed, self._output_dir)
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
