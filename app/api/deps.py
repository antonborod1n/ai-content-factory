"""FastAPI dependency providers."""

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.project_paths import articles_output_for_slug, topics_file_for_slug
from app.db.models.project import Project
from app.db.session import check_database_connection, get_db_session
from app.repositories.article_repository import ArticleRepository
from app.repositories.discovery_repository import DiscoveryRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.research_repository import ResearchRepository
from app.repositories.run_repository import RunRepository
from app.services.ai.analyst import CompetitorAnalyst
from app.services.ai.base import AIWriter
from app.services.ai.content_gap import ContentGapAnalyst
from app.services.ai.detector import AiDetector
from app.services.ai.dzen_writer import DzenWriter
from app.services.ai.editor import Editor
from app.services.ai.embedder import Embedder
from app.services.ai.fact_checker import FactChecker
from app.services.ai.humanizer import Humanizer
from app.services.ai.image_provider import ImageProvider
from app.services.ai.openai_analyst import OpenAICompetitorAnalyst
from app.services.ai.openai_content_gap import OpenAIContentGapAnalyst
from app.services.ai.openai_detector import OpenAIDetector
from app.services.ai.openai_dzen import OpenAIDzenWriter
from app.services.ai.openai_editor import OpenAIEditor
from app.services.ai.openai_embedder import OpenAIEmbedder
from app.services.ai.openai_fact_checker import OpenAIFactChecker
from app.services.ai.openai_humanizer import OpenAIHumanizer
from app.services.ai.openai_image import OpenAIImageProvider
from app.services.ai.openai_seo_agent import OpenAISeoAgent
from app.services.ai.openai_summarizer import OpenAISummarizer
from app.services.ai.openai_topic_planner import OpenAITopicPlanner
from app.services.ai.openai_writer import OpenAIWriter
from app.services.ai.seo_agent import SeoAgent
from app.services.ai.summarizer import Summarizer
from app.services.ai.topic_planner import TopicPlanner
from app.services.article_service import ArticleService
from app.services.competitor_topics_service import CompetitorTopicsService
from app.services.discovery.routing import RoutingSerpSnapshotProvider
from app.services.discovery.serper_snapshot import SerperSnapshotProvider
from app.services.discovery.snapshotter import SerpSnapshotProvider
from app.services.discovery.yandex_serpapi import YandexSerpApiProvider
from app.services.discovery_service import DiscoveryService
from app.services.document_service import DocumentService
from app.services.dzen_service import DzenService
from app.services.image_service import ImageService
from app.services.linking_service import LinkingService
from app.services.pipeline_service import PipelineService
from app.services.quality_service import QualityService
from app.services.rag_service import RagService
from app.services.research.page_fetcher import HttpPageFetcher, PageFetcher
from app.services.research.searcher import SearchProvider
from app.services.research.serper_searcher import SerperSearchProvider
from app.services.research_service import ResearchService
from app.services.run_service import RunService
from app.services.run_tracker import RunTracker

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_database_health() -> bool:
    """True when the database answers a trivial query."""
    return await check_database_connection()


DatabaseHealthDep = Annotated[bool, Depends(get_database_health)]


def get_project_repository(session: SessionDep) -> ProjectRepository:
    return ProjectRepository(session)


async def require_project(
    session: SessionDep,
    x_project_id: Annotated[uuid.UUID | None, Header()] = None,
    x_project_slug: Annotated[str | None, Header()] = None,
    project: Annotated[uuid.UUID | None, Query()] = None,
) -> Project:
    """Working endpoints must name one project. Missing header is 422.

    Query ``project`` is accepted so ``<img src>`` can load article media
    without custom headers.
    """
    repository = ProjectRepository(session)
    slug = (x_project_slug or "").strip()
    project_id = x_project_id or project
    if project_id is None and not slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="X-Project-Id or X-Project-Slug is required",
        )
    if project_id is not None:
        found = await repository.get_by_id(project_id)
    else:
        found = await repository.get_by_slug(slug)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return found


ProjectDep = Annotated[Project, Depends(require_project)]
ProjectRepositoryDep = Annotated[ProjectRepository, Depends(get_project_repository)]


def get_article_repository(
    session: SessionDep, project: ProjectDep
) -> ArticleRepository:
    return ArticleRepository(session, project_id=project.id)


def get_document_repository(
    session: SessionDep, project: ProjectDep
) -> DocumentRepository:
    return DocumentRepository(session, project_id=project.id)


def get_research_repository(
    session: SessionDep, project: ProjectDep
) -> ResearchRepository:
    return ResearchRepository(session, project_id=project.id)


def get_run_repository(session: SessionDep, project: ProjectDep) -> RunRepository:
    return RunRepository(session, project_id=project.id)


def get_run_tracker(
    repository: Annotated[RunRepository, Depends(get_run_repository)],
) -> RunTracker:
    return RunTracker(repository, log_path=get_settings().runs_log_path)


def get_run_service(
    repository: Annotated[RunRepository, Depends(get_run_repository)],
) -> RunService:
    return RunService(repository)


def get_discovery_repository(
    session: SessionDep, project: ProjectDep
) -> DiscoveryRepository:
    return DiscoveryRepository(session, project_id=project.id)


def get_ai_writer() -> AIWriter:
    """Runtime writer. Tests override this with MockAIWriter."""
    return OpenAIWriter()


def get_embedder() -> Embedder:
    """Runtime embedder. Tests override this with MockEmbedder."""
    return OpenAIEmbedder()


def get_search_provider() -> SearchProvider:
    """Runtime SERP client. Tests override this with MockSearchProvider."""
    return SerperSearchProvider()


def get_page_fetcher() -> PageFetcher:
    """Runtime HTML fetcher. Tests override this with MockPageFetcher."""
    return HttpPageFetcher()


def get_competitor_analyst() -> CompetitorAnalyst:
    """Runtime outline planner. Tests override this with MockCompetitorAnalyst."""
    return OpenAICompetitorAnalyst()


def get_seo_agent() -> SeoAgent:
    """Runtime SEO planner. Tests override this with MockSeoAgent."""
    return OpenAISeoAgent()


def get_fact_checker() -> FactChecker:
    """Runtime fact checker. Tests override this with MockFactChecker."""
    return OpenAIFactChecker()


def get_editor() -> Editor:
    """Runtime editor. Tests override this with MockEditor."""
    return OpenAIEditor()


def get_image_provider() -> ImageProvider:
    """Runtime image generator. Tests override this with MockImageProvider."""
    return OpenAIImageProvider()


def get_dzen_writer() -> DzenWriter:
    """Runtime Dzen writer. Tests override this with MockDzenWriter."""
    return OpenAIDzenWriter()


def get_ai_detector() -> AiDetector:
    """Runtime detector. Tests override this with MockAiDetector."""
    return OpenAIDetector()


def get_humanizer() -> Humanizer:
    """Runtime humanizer. Tests override this with MockHumanizer."""
    return OpenAIHumanizer()


def get_summarizer() -> Summarizer:
    """Runtime summarizer. Tests override this with MockSummarizer."""
    return OpenAISummarizer()


def get_topic_planner() -> TopicPlanner:
    """Runtime topic planner. Tests override this with MockTopicPlanner."""
    return OpenAITopicPlanner()


def get_content_gap_analyst() -> ContentGapAnalyst:
    """Runtime content-gap analyst. Tests override with MockContentGapAnalyst."""
    return OpenAIContentGapAnalyst()


def get_serp_snapshot_provider() -> SerpSnapshotProvider:
    """Runtime Google + Yandex snapshot router. Tests override with a mock."""
    return RoutingSerpSnapshotProvider(
        google=SerperSnapshotProvider(),
        yandex=YandexSerpApiProvider(),
    )


def get_rag_service(
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> RagService:
    return RagService(repository, embedder)


def get_document_service(
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    runs: Annotated[RunTracker, Depends(get_run_tracker)],
) -> DocumentService:
    return DocumentService(repository, embedder, run_tracker=runs)


def get_discovery_service(
    repository: Annotated[DiscoveryRepository, Depends(get_discovery_repository)],
    snapshotter: Annotated[SerpSnapshotProvider, Depends(get_serp_snapshot_provider)],
    planner: Annotated[TopicPlanner, Depends(get_topic_planner)],
    runs: Annotated[RunTracker, Depends(get_run_tracker)],
    project: ProjectDep,
) -> DiscoveryService:
    return DiscoveryService(
        repository,
        snapshotter,
        planner,
        topics_file_path=str(topics_file_for_slug(project.slug)),
        run_tracker=runs,
    )


def get_competitor_topics_service(
    repository: Annotated[DiscoveryRepository, Depends(get_discovery_repository)],
    analyst: Annotated[ContentGapAnalyst, Depends(get_content_gap_analyst)],
    runs: Annotated[RunTracker, Depends(get_run_tracker)],
    project: ProjectDep,
) -> CompetitorTopicsService:
    return CompetitorTopicsService(
        repository,
        analyst,
        topics_file_path=str(topics_file_for_slug(project.slug)),
        run_tracker=runs,
    )


def get_research_service(
    repository: Annotated[ResearchRepository, Depends(get_research_repository)],
    searcher: Annotated[SearchProvider, Depends(get_search_provider)],
    fetcher: Annotated[PageFetcher, Depends(get_page_fetcher)],
    analyst: Annotated[CompetitorAnalyst, Depends(get_competitor_analyst)],
    runs: Annotated[RunTracker, Depends(get_run_tracker)],
) -> ResearchService:
    return ResearchService(repository, searcher, fetcher, analyst, run_tracker=runs)


def get_image_service(
    provider: Annotated[ImageProvider, Depends(get_image_provider)],
) -> ImageService:
    return ImageService(provider)


def get_linking_service(
    repository: Annotated[ArticleRepository, Depends(get_article_repository)],
) -> LinkingService:
    return LinkingService(repository)


def get_dzen_service(
    writer: Annotated[DzenWriter, Depends(get_dzen_writer)],
    image_service: Annotated[ImageService, Depends(get_image_service)],
) -> DzenService:
    return DzenService(writer, image_service=image_service)


def get_quality_service(
    detector: Annotated[AiDetector, Depends(get_ai_detector)],
    humanizer: Annotated[Humanizer, Depends(get_humanizer)],
    summarizer: Annotated[Summarizer, Depends(get_summarizer)],
) -> QualityService:
    return QualityService(detector, humanizer, summarizer)


def get_pipeline_service(
    writer: Annotated[AIWriter, Depends(get_ai_writer)],
    seo_agent: Annotated[SeoAgent, Depends(get_seo_agent)],
    fact_checker: Annotated[FactChecker, Depends(get_fact_checker)],
    editor: Annotated[Editor, Depends(get_editor)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    research_service: Annotated[ResearchService, Depends(get_research_service)],
    runs: Annotated[RunTracker, Depends(get_run_tracker)],
) -> PipelineService:
    return PipelineService(
        writer,
        seo_agent,
        fact_checker,
        editor,
        rag_service=rag_service,
        research_service=research_service,
        run_tracker=runs,
    )


def get_article_service(
    repository: Annotated[ArticleRepository, Depends(get_article_repository)],
    writer: Annotated[AIWriter, Depends(get_ai_writer)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    research_service: Annotated[ResearchService, Depends(get_research_service)],
    pipeline_service: Annotated[PipelineService, Depends(get_pipeline_service)],
    image_service: Annotated[ImageService, Depends(get_image_service)],
    linking_service: Annotated[LinkingService, Depends(get_linking_service)],
    dzen_service: Annotated[DzenService, Depends(get_dzen_service)],
    quality_service: Annotated[QualityService, Depends(get_quality_service)],
    runs: Annotated[RunTracker, Depends(get_run_tracker)],
    project: ProjectDep,
) -> ArticleService:
    return ArticleService(
        repository,
        writer,
        rag_service=rag_service,
        research_service=research_service,
        pipeline_service=pipeline_service,
        image_service=image_service,
        linking_service=linking_service,
        dzen_service=dzen_service,
        quality_service=quality_service,
        run_tracker=runs,
        output_dir=articles_output_for_slug(project.slug),
    )


ArticleServiceDep = Annotated[ArticleService, Depends(get_article_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
RagServiceDep = Annotated[RagService, Depends(get_rag_service)]
ResearchServiceDep = Annotated[ResearchService, Depends(get_research_service)]
RunServiceDep = Annotated[RunService, Depends(get_run_service)]
DiscoveryServiceDep = Annotated[DiscoveryService, Depends(get_discovery_service)]
CompetitorTopicsServiceDep = Annotated[
    CompetitorTopicsService, Depends(get_competitor_topics_service)
]
