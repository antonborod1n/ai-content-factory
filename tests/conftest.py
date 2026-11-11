"""Shared pytest fixtures."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.db_setup import derive_test_database_url

# When tests run on the host, point them at Compose-published Postgres using the
# POSTGRES_* values from the environment. Credentials never live in code.
if "DATABASE_URL" not in os.environ and os.environ.get("POSTGRES_PASSWORD"):
    _user = os.environ.get("POSTGRES_USER", "acf")
    _database = os.environ.get("POSTGRES_DB", "acf")
    _password = os.environ["POSTGRES_PASSWORD"]
    os.environ["DATABASE_URL"] = (
        f"postgresql+asyncpg://{_user}:{_password}@localhost:15432/{_database}"
    )

# Tests truncate tables, so they always run against a separate database.
if "DATABASE_URL" in os.environ:
    os.environ["DATABASE_URL"] = derive_test_database_url(os.environ["DATABASE_URL"])

# Do not litter the workspace with Markdown files from API/service tests.
os.environ["ARTICLES_OUTPUT_DIR"] = ""
os.environ["TOPICS_FILE_PATH"] = ""
os.environ["RUNS_LOG_PATH"] = str(Path(tempfile.gettempdir()) / "acf-pytest-runs.jsonl")
os.environ.setdefault("APP_ENV", "test")

from app.api.deps import (
    get_ai_detector,
    get_ai_writer,
    get_competitor_analyst,
    get_content_gap_analyst,
    get_dzen_writer,
    get_editor,
    get_embedder,
    get_fact_checker,
    get_humanizer,
    get_image_provider,
    get_page_fetcher,
    get_search_provider,
    get_seo_agent,
    get_serp_snapshot_provider,
    get_summarizer,
    get_topic_planner,
)
from app.config import get_settings
from app.db.models.project import DEFAULT_PROJECT_ID
from app.db.session import (
    dispose_engine,
    get_session_factory,
    init_engine,
    reset_engine_state,
)
from app.main import create_app
from app.repositories.article_repository import ArticleRepository
from app.repositories.discovery_repository import DiscoveryRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.research_repository import ResearchRepository
from app.services.ai.mock_analyst import MockCompetitorAnalyst
from app.services.ai.mock_content_gap import MockContentGapAnalyst
from app.services.ai.mock_detector import MockAiDetector
from app.services.ai.mock_dzen import MockDzenWriter
from app.services.ai.mock_editor import MockEditor
from app.services.ai.mock_embedder import MockEmbedder
from app.services.ai.mock_fact_checker import MockFactChecker
from app.services.ai.mock_humanizer import MockHumanizer
from app.services.ai.mock_image import MockImageProvider
from app.services.ai.mock_seo_agent import MockSeoAgent
from app.services.ai.mock_summarizer import MockSummarizer
from app.services.ai.mock_topic_planner import MockTopicPlanner
from app.services.ai.mock_writer import MockAIWriter
from app.services.discovery.mock_snapshotter import MockSerpSnapshotProvider
from app.services.research.mock_page_fetcher import MockPageFetcher
from app.services.research.mock_searcher import MockSearchProvider

_TRUNCATE_SQL = (
    "TRUNCATE TABLE run_steps, runs, content_plan_topics, content_plans, "
    "research_competitors, research_runs, "
    "chunks, documents, articles, projects RESTART IDENTITY CASCADE"
)
_SEED_PROJECT_SQL = (
    "INSERT INTO projects (id, slug, name, language) VALUES "
    "('00000000-0000-4000-8000-000000000001', 'default', 'Default', 'ru')"
)


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_database() -> None:
    """Create the test database and migrate it once per session.

    Runs in a subprocess so Alembic's own event loop cannot clash with the
    pytest-asyncio loop.
    """
    subprocess.run(
        [sys.executable, "-m", "tests.db_setup"],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _topics_dir(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Exports may only write under TOPICS_DIR; every tmp_path lives below this."""
    os.environ["TOPICS_DIR"] = str(tmp_path_factory.getbasetemp())


@pytest.fixture(autouse=True)
async def _reset_db_engine() -> None:
    get_settings.cache_clear()
    reset_engine_state()
    init_engine()
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(text(_TRUNCATE_SQL))
        await session.execute(text(_SEED_PROJECT_SQL))
        await session.commit()
    yield
    await dispose_engine()
    reset_engine_state()
    get_settings.cache_clear()


@pytest.fixture
def api_app() -> FastAPI:
    """Fresh application instance; tests may set dependency_overrides on it."""
    application = create_app()
    application.dependency_overrides[get_ai_writer] = lambda: MockAIWriter()
    application.dependency_overrides[get_embedder] = lambda: MockEmbedder()
    application.dependency_overrides[get_search_provider] = lambda: MockSearchProvider()
    application.dependency_overrides[get_page_fetcher] = lambda: MockPageFetcher()
    application.dependency_overrides[get_competitor_analyst] = lambda: (
        MockCompetitorAnalyst()
    )
    application.dependency_overrides[get_content_gap_analyst] = lambda: (
        MockContentGapAnalyst()
    )
    application.dependency_overrides[get_seo_agent] = lambda: MockSeoAgent()
    application.dependency_overrides[get_fact_checker] = lambda: MockFactChecker()
    application.dependency_overrides[get_editor] = lambda: MockEditor()
    application.dependency_overrides[get_image_provider] = lambda: MockImageProvider()
    application.dependency_overrides[get_dzen_writer] = lambda: MockDzenWriter()
    application.dependency_overrides[get_ai_detector] = lambda: MockAiDetector()
    application.dependency_overrides[get_humanizer] = lambda: MockHumanizer()
    application.dependency_overrides[get_summarizer] = lambda: MockSummarizer()
    application.dependency_overrides[get_serp_snapshot_provider] = lambda: (
        MockSerpSnapshotProvider()
    )
    application.dependency_overrides[get_topic_planner] = lambda: MockTopicPlanner()
    return application


@pytest.fixture
async def client(api_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers["X-Project-Id"] = str(DEFAULT_PROJECT_ID)
        yield ac


@pytest.fixture
async def db_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(text(_TRUNCATE_SQL))
        await session.execute(text(_SEED_PROJECT_SQL))
        await session.commit()
        yield session
        await session.execute(text(_TRUNCATE_SQL))
        await session.execute(text(_SEED_PROJECT_SQL))
        await session.commit()


@pytest.fixture
async def article_repository(db_session: AsyncSession) -> ArticleRepository:
    return ArticleRepository(db_session, project_id=DEFAULT_PROJECT_ID)


@pytest.fixture
async def document_repository(db_session: AsyncSession) -> DocumentRepository:
    return DocumentRepository(db_session, project_id=DEFAULT_PROJECT_ID)


@pytest.fixture
async def research_repository(db_session: AsyncSession) -> ResearchRepository:
    return ResearchRepository(db_session, project_id=DEFAULT_PROJECT_ID)


@pytest.fixture
async def discovery_repository(db_session: AsyncSession) -> DiscoveryRepository:
    return DiscoveryRepository(db_session, project_id=DEFAULT_PROJECT_ID)
