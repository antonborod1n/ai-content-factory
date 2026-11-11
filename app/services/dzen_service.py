"""Write a shorter Dzen version of a completed article."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.core.exceptions import AIConfigurationError, AIError
from app.core.word_count import count_characters
from app.schemas.dzen import (
    DzenArticle,
    DzenArticleOutput,
    DzenWriteInput,
    DzenWriteResult,
)
from app.schemas.enrichment import ArticleAsset, GeneratedAsset
from app.services.ai.dzen_writer import DzenWriter
from app.services.image_service import ImageService

logger = logging.getLogger(__name__)


class DzenService:
    """Orchestrates Dzen write + optional 3 images. No SQL, no SDK."""

    def __init__(
        self,
        writer: DzenWriter,
        *,
        image_service: ImageService | None = None,
        enabled: bool | None = None,
        target_char_count: int | None = None,
    ) -> None:
        settings = get_settings()
        self._writer = writer
        self._image_service = image_service
        self._enabled = settings.dzen_enabled if enabled is None else enabled
        self._target_char_count = (
            settings.dzen_target_char_count
            if target_char_count is None
            else target_char_count
        )

    async def write(
        self,
        *,
        source_title: str,
        source_markdown: str,
        language: str,
        audience: str,
        use_images: bool,
    ) -> DzenWriteResult:
        if not self._enabled:
            logger.info("Dzen channel disabled; skipping")
            return DzenWriteResult(article=DzenArticle(status="skipped"))

        request = DzenWriteInput(
            source_title=source_title,
            source_markdown=source_markdown,
            language=language,
            audience=audience,
            target_char_count=self._target_char_count,
        )
        try:
            output = await self._writer.generate(request)
        except AIConfigurationError:
            logger.info("Dzen writer is not configured; skipping")
            return DzenWriteResult(article=DzenArticle(status="skipped"))
        except AIError:
            logger.warning("Dzen writing failed; main article is unchanged")
            return DzenWriteResult(article=DzenArticle(status="failed"))
        except Exception:
            logger.exception("Unexpected error while writing Dzen version")
            return DzenWriteResult(article=DzenArticle(status="failed"))

        markdown, generated = await self._maybe_images(
            output, source_title=source_title, use_images=use_images
        )
        article = DzenArticle(
            status="completed",
            title=output.title,
            content_markdown=markdown,
            char_count=count_characters(markdown),
            assets=[_asset_metadata(item) for item in generated],
        )
        logger.info("Dzen version finished chars=%s", article.char_count)
        return DzenWriteResult(article=article, assets=generated)

    async def _maybe_images(
        self,
        output: DzenArticleOutput,
        *,
        source_title: str,
        use_images: bool,
    ) -> tuple[str, list[GeneratedAsset]]:
        markdown = output.content_markdown
        if not use_images or self._image_service is None:
            return markdown, []
        return await self._image_service.replace_placeholders(
            markdown, topic=source_title, kinds={"cover", "dzen"}
        )


def _asset_metadata(item: GeneratedAsset) -> ArticleAsset:
    return ArticleAsset.model_validate(item.model_dump())
