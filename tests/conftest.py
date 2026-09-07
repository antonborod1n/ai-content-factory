"""Shared pytest fixtures."""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Prefer localhost when tests run on the host against Compose-published Postgres.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://acf:acf_secret@localhost:5432/acf",
)

from app.config import get_settings
from app.db.session import (
    dispose_engine,
    get_session_factory,
    init_engine,
    reset_engine_state,
)
from app.main import create_app
from app.repositories.article_repository import ArticleRepository


@pytest.fixture(autouse=True)
async def _reset_db_engine() -> None:
    get_settings.cache_clear()
    reset_engine_state()
    init_engine()
    yield
    await dispose_engine()
    reset_engine_state()
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncClient:
    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(text("TRUNCATE TABLE articles RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session
        await session.execute(text("TRUNCATE TABLE articles RESTART IDENTITY CASCADE"))
        await session.commit()


@pytest.fixture
async def article_repository(db_session: AsyncSession) -> ArticleRepository:
    return ArticleRepository(db_session)
