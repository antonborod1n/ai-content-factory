"""FastAPI dependency providers."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.article_repository import ArticleRepository
from app.services.ai.base import AIWriter
from app.services.ai.openai_writer import OpenAIWriter
from app.services.article_service import ArticleService

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_article_repository(session: SessionDep) -> ArticleRepository:
    return ArticleRepository(session)


def get_ai_writer() -> AIWriter:
    """Runtime writer. Tests override this with MockAIWriter."""
    return OpenAIWriter()


def get_article_service(
    repository: Annotated[ArticleRepository, Depends(get_article_repository)],
    writer: Annotated[AIWriter, Depends(get_ai_writer)],
) -> ArticleService:
    return ArticleService(repository, writer)


ArticleServiceDep = Annotated[ArticleService, Depends(get_article_service)]
