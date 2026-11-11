"""Article persistence operations (no business logic)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.db.models.article import Article, ArticleStatus, ReviewStatus

_LIST_DEFER = (
    defer(Article.content_markdown),
    defer(Article.meta_description),
    defer(Article.audience),
    defer(Article.keywords),
    defer(Article.error_message),
    defer(Article.pipeline),
    defer(Article.assets),
    defer(Article.internal_links),
    defer(Article.dzen),
    defer(Article.quality),
    defer(Article.competitor_sources),
)


class ArticleRepository:
    """Database access for the articles table."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
    ) -> None:
        self._session = session
        self._project_id = project_id

    async def create(
        self,
        *,
        topic: str,
        language: str = "ru",
        audience: str = "general",
        keywords: list[str] | None = None,
        status: ArticleStatus = ArticleStatus.PENDING,
        title: str | None = None,
        meta_description: str | None = None,
        content_markdown: str | None = None,
        word_count: int | None = None,
        error_message: str | None = None,
    ) -> Article:
        article = Article(
            project_id=self._project_id,
            topic=topic,
            language=language,
            audience=audience,
            keywords=keywords if keywords is not None else [],
            status=status,
            title=title,
            meta_description=meta_description,
            content_markdown=content_markdown,
            word_count=word_count,
            error_message=error_message,
        )
        self._session.add(article)
        await self._session.commit()
        await self._session.refresh(article)
        return article

    async def get_by_id(self, article_id: uuid.UUID) -> Article | None:
        article = await self._session.get(Article, article_id)
        if article is None or article.project_id != self._project_id:
            return None
        return article

    async def update(self, article_id: uuid.UUID, **fields: Any) -> Article | None:
        article = await self.get_by_id(article_id)
        if article is None:
            return None

        for key, value in fields.items():
            if not hasattr(article, key):
                msg = f"Unknown article field: {key}"
                raise ValueError(msg)
            setattr(article, key, value)

        await self._session.commit()
        await self._session.refresh(article)
        return article

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: ArticleStatus | None = None,
        review_status: ReviewStatus | None = None,
    ) -> list[Article]:
        statement = (
            select(Article)
            .options(*_LIST_DEFER)
            .where(Article.project_id == self._project_id)
            .order_by(Article.created_at.desc())
        )
        if status is not None:
            statement = statement.where(Article.status == status)
        if review_status is not None:
            statement = statement.where(Article.review_status == review_status)
        statement = statement.limit(limit).offset(offset)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        status: ArticleStatus | None = None,
        review_status: ReviewStatus | None = None,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(Article)
            .where(Article.project_id == self._project_id)
        )
        if status is not None:
            statement = statement.where(Article.status == status)
        if review_status is not None:
            statement = statement.where(Article.review_status == review_status)
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_link_targets(
        self,
        *,
        language: str,
        exclude_id: uuid.UUID,
        limit: int = 50,
    ) -> list[Article]:
        """Completed articles that can be used as internal-link destinations."""
        statement = (
            select(Article)
            .where(Article.project_id == self._project_id)
            .where(Article.status == ArticleStatus.COMPLETED)
            .where(Article.id != exclude_id)
            .where(Article.language == language)
            .where(Article.url_slug.isnot(None))
            .where(Article.url_slug != "")
            .where(Article.title.isnot(None))
            .order_by(Article.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
