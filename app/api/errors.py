"""Exception handlers mapping domain errors to sanitized HTTP responses."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ArticleGenerationError,
    ArticleGenerationUpstreamError,
    ArticleNotFoundError,
    CompetitorTopicsConfigurationError,
    CompetitorTopicsError,
    CompetitorTopicsNotFoundError,
    CompetitorTopicsParseError,
    CompetitorTopicsUpstreamError,
    DiscoveryConfigurationError,
    DiscoveryError,
    DiscoveryNotFoundError,
    DiscoveryUpstreamError,
    DocumentIngestError,
    DocumentIngestUpstreamError,
    DocumentNotFoundError,
    DocumentParseError,
    ResearchConfigurationError,
    ResearchError,
    ResearchNotFoundError,
    ResearchUpstreamError,
)
from app.schemas.articles import ArticleErrorResponse
from app.schemas.competitor_topics import CompetitorTopicsErrorResponse
from app.schemas.discovery import DiscoveryErrorResponse
from app.schemas.documents import DocumentErrorResponse
from app.schemas.research import ResearchErrorResponse

logger = logging.getLogger(__name__)


def _article_error(
    exc: ArticleGenerationError, status_code: int
) -> JSONResponse:
    payload = ArticleErrorResponse(detail=exc.message, id=exc.article_id)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


def _document_error(
    exc: DocumentIngestError | DocumentNotFoundError | DocumentParseError,
    status_code: int,
) -> JSONResponse:
    status_value = None
    if isinstance(exc, DocumentNotFoundError):
        status_value = None
    payload = DocumentErrorResponse(
        detail=exc.message,
        id=exc.document_id,
        status=status_value,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(ArticleNotFoundError)
    async def handle_article_not_found(
        _request: Request, exc: ArticleNotFoundError
    ) -> JSONResponse:
        return _article_error(exc, status.HTTP_404_NOT_FOUND)

    @application.exception_handler(ArticleGenerationUpstreamError)
    async def handle_upstream_error(
        _request: Request, exc: ArticleGenerationUpstreamError
    ) -> JSONResponse:
        logger.warning("Article generation failed upstream: %s", exc.message)
        return _article_error(exc, status.HTTP_502_BAD_GATEWAY)

    @application.exception_handler(ArticleGenerationError)
    async def handle_generation_error(
        _request: Request, exc: ArticleGenerationError
    ) -> JSONResponse:
        logger.error("Article generation failed: %s", exc.message)
        return _article_error(exc, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @application.exception_handler(DocumentParseError)
    async def handle_document_parse(
        _request: Request, exc: DocumentParseError
    ) -> JSONResponse:
        return _document_error(exc, status.HTTP_422_UNPROCESSABLE_CONTENT)

    @application.exception_handler(DocumentNotFoundError)
    async def handle_document_not_found(
        _request: Request, exc: DocumentNotFoundError
    ) -> JSONResponse:
        return _document_error(exc, status.HTTP_404_NOT_FOUND)

    @application.exception_handler(DocumentIngestUpstreamError)
    async def handle_document_upstream(
        _request: Request, exc: DocumentIngestUpstreamError
    ) -> JSONResponse:
        logger.warning("Document ingest failed upstream: %s", exc.message)
        payload = DocumentErrorResponse(
            detail=exc.message,
            id=exc.document_id,
            status="failed",
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=payload.model_dump(mode="json"),
        )

    @application.exception_handler(DocumentIngestError)
    async def handle_document_ingest(
        _request: Request, exc: DocumentIngestError
    ) -> JSONResponse:
        logger.error("Document ingest failed: %s", exc.message)
        payload = DocumentErrorResponse(
            detail=exc.message,
            id=exc.document_id,
            status="failed",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload.model_dump(mode="json"),
        )

    def _research_error(
        exc: ResearchError, status_code: int, *, status_value: str | None
    ) -> JSONResponse:
        payload = ResearchErrorResponse(
            detail=exc.message,
            id=exc.research_id,
            status=status_value,
        )
        return JSONResponse(
            status_code=status_code,
            content=payload.model_dump(mode="json"),
        )

    @application.exception_handler(ResearchNotFoundError)
    async def handle_research_not_found(
        _request: Request, exc: ResearchNotFoundError
    ) -> JSONResponse:
        return _research_error(exc, status.HTTP_404_NOT_FOUND, status_value=None)

    @application.exception_handler(ResearchConfigurationError)
    async def handle_research_config(
        _request: Request, exc: ResearchConfigurationError
    ) -> JSONResponse:
        logger.error("Competitor research is not configured: %s", exc.message)
        return _research_error(
            exc, status.HTTP_500_INTERNAL_SERVER_ERROR, status_value="failed"
        )

    @application.exception_handler(ResearchUpstreamError)
    async def handle_research_upstream(
        _request: Request, exc: ResearchUpstreamError
    ) -> JSONResponse:
        logger.warning("Competitor research failed upstream: %s", exc.message)
        return _research_error(
            exc, status.HTTP_502_BAD_GATEWAY, status_value="failed"
        )

    @application.exception_handler(ResearchError)
    async def handle_research_error(
        _request: Request, exc: ResearchError
    ) -> JSONResponse:
        logger.error("Competitor research failed: %s", exc.message)
        return _research_error(
            exc, status.HTTP_500_INTERNAL_SERVER_ERROR, status_value="failed"
        )

    def _discovery_error(
        exc: DiscoveryError, status_code: int, *, status_value: str | None
    ) -> JSONResponse:
        payload = DiscoveryErrorResponse(
            detail=exc.message,
            id=exc.plan_id,
            status=status_value,
        )
        return JSONResponse(
            status_code=status_code,
            content=payload.model_dump(mode="json"),
        )

    @application.exception_handler(DiscoveryNotFoundError)
    async def handle_discovery_not_found(
        _request: Request, exc: DiscoveryNotFoundError
    ) -> JSONResponse:
        return _discovery_error(exc, status.HTTP_404_NOT_FOUND, status_value=None)

    @application.exception_handler(DiscoveryConfigurationError)
    async def handle_discovery_config(
        _request: Request, exc: DiscoveryConfigurationError
    ) -> JSONResponse:
        logger.error("Topic discovery is not configured: %s", exc.message)
        return _discovery_error(
            exc, status.HTTP_500_INTERNAL_SERVER_ERROR, status_value="failed"
        )

    @application.exception_handler(DiscoveryUpstreamError)
    async def handle_discovery_upstream(
        _request: Request, exc: DiscoveryUpstreamError
    ) -> JSONResponse:
        logger.warning("Topic discovery failed upstream: %s", exc.message)
        return _discovery_error(
            exc, status.HTTP_502_BAD_GATEWAY, status_value="failed"
        )

    @application.exception_handler(DiscoveryError)
    async def handle_discovery_error(
        _request: Request, exc: DiscoveryError
    ) -> JSONResponse:
        logger.error("Topic discovery failed: %s", exc.message)
        return _discovery_error(
            exc, status.HTTP_500_INTERNAL_SERVER_ERROR, status_value="failed"
        )

    def _competitor_topics_error(
        exc: CompetitorTopicsError, status_code: int, *, status_value: str | None
    ) -> JSONResponse:
        payload = CompetitorTopicsErrorResponse(
            detail=exc.message,
            id=exc.plan_id,
            status=status_value,
        )
        return JSONResponse(
            status_code=status_code,
            content=payload.model_dump(mode="json"),
        )

    @application.exception_handler(CompetitorTopicsNotFoundError)
    async def handle_competitor_topics_not_found(
        _request: Request, exc: CompetitorTopicsNotFoundError
    ) -> JSONResponse:
        return _competitor_topics_error(
            exc, status.HTTP_404_NOT_FOUND, status_value=None
        )

    @application.exception_handler(CompetitorTopicsConfigurationError)
    async def handle_competitor_topics_config(
        _request: Request, exc: CompetitorTopicsConfigurationError
    ) -> JSONResponse:
        logger.error("Competitor topic import is not configured: %s", exc.message)
        return _competitor_topics_error(
            exc, status.HTTP_500_INTERNAL_SERVER_ERROR, status_value="failed"
        )

    @application.exception_handler(CompetitorTopicsParseError)
    async def handle_competitor_topics_parse(
        _request: Request, exc: CompetitorTopicsParseError
    ) -> JSONResponse:
        return _competitor_topics_error(
            exc, status.HTTP_422_UNPROCESSABLE_CONTENT, status_value="failed"
        )

    @application.exception_handler(CompetitorTopicsUpstreamError)
    async def handle_competitor_topics_upstream(
        _request: Request, exc: CompetitorTopicsUpstreamError
    ) -> JSONResponse:
        logger.warning("Competitor topic analysis failed upstream: %s", exc.message)
        return _competitor_topics_error(
            exc, status.HTTP_502_BAD_GATEWAY, status_value="failed"
        )

    @application.exception_handler(CompetitorTopicsError)
    async def handle_competitor_topics_error(
        _request: Request, exc: CompetitorTopicsError
    ) -> JSONResponse:
        logger.error("Competitor topic import failed: %s", exc.message)
        return _competitor_topics_error(
            exc, status.HTTP_500_INTERNAL_SERVER_ERROR, status_value="failed"
        )
