"""Article persistence operations (no business logic)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.article import Article, ArticleStatus


class ArticleRepository:
    """Database access for the articles table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        return await self._session.get(Article, article_id)

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
    ) -> list[Article]:
        statement = select(Article).order_by(Article.created_at.desc())
        if status is not None:
            statement = statement.where(Article.status == status)
        statement = statement.limit(limit).offset(offset)
        result = await self._session.execute(statement)
        return list(result.scalars().all())
