"""Shared pytest fixtures."""

import os

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# When tests run on the host, point them at Compose-published Postgres using the
# POSTGRES_* values from the environment. Credentials never live in code.
if "DATABASE_URL" not in os.environ and os.environ.get("POSTGRES_PASSWORD"):
    _user = os.environ.get("POSTGRES_USER", "acf")
    _database = os.environ.get("POSTGRES_DB", "acf")
    _password = os.environ["POSTGRES_PASSWORD"]
    os.environ["DATABASE_URL"] = (
        f"postgresql+asyncpg://{_user}:{_password}@localhost:5432/{_database}"
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
def api_app() -> FastAPI:
    """Fresh application instance; tests may set dependency_overrides on it."""
    return create_app()


@pytest.fixture
async def client(api_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=api_app)
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
