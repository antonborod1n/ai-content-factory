"""Insert markdown links to other completed articles."""

from __future__ import annotations

import logging
import uuid

from app.config import get_settings
from app.core.internal_links import LinkTarget, insert_internal_links
from app.db.models.article import Article
from app.repositories.article_repository import ArticleRepository
from app.schemas.enrichment import InternalLinkRef

logger = logging.getLogger(__name__)


class LinkingService:
    """Finds related completed articles and inserts a few in-body links."""

    def __init__(
        self,
        repository: ArticleRepository,
        *,
        enabled: bool | None = None,
        max_links: int | None = None,
        href_prefix: str | None = None,
    ) -> None:
        settings = get_settings()
        self._repository = repository
        self._enabled = (
            settings.internal_links_enabled if enabled is None else enabled
        )
        self._max_links = (
            settings.internal_link_max if max_links is None else max_links
        )
        self._href_prefix = (
            settings.internal_link_prefix if href_prefix is None else href_prefix
        )

    async def insert_links(
        self,
        markdown: str,
        *,
        article_id: uuid.UUID,
        language: str,
        keywords: list[str],
        topic: str,
    ) -> tuple[str, list[InternalLinkRef]]:
        if not self._enabled:
            return markdown, []
        rows = await self._repository.list_link_targets(
            language=language,
            exclude_id=article_id,
        )
        targets = [_to_target(row) for row in rows]
        updated, inserted = insert_internal_links(
            markdown,
            targets,
            keywords=keywords,
            topic=topic,
            max_links=self._max_links,
            href_prefix=self._href_prefix,
        )
        refs = [
            InternalLinkRef(
                title=item.title, url_slug=item.url_slug, anchor=item.anchor
            )
            for item in inserted
        ]
        if refs:
            logger.info("Internal links inserted count=%s", len(refs))
        return updated, refs


def _to_target(row: Article) -> LinkTarget:
    keywords = row.keywords if isinstance(row.keywords, list) else []
    return LinkTarget(
        title=row.title or row.topic,
        url_slug=row.url_slug or "",
        topic=row.topic,
        keywords=tuple(str(item) for item in keywords),
    )
