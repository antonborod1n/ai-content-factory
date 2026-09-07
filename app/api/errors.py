"""Exception handlers mapping domain errors to sanitized HTTP responses."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import ArticleGenerationError, ArticleGenerationUpstreamError
from app.schemas.articles import ArticleErrorResponse

logger = logging.getLogger(__name__)


def _error_response(
    exc: ArticleGenerationError, status_code: int
) -> JSONResponse:
    payload = ArticleErrorResponse(detail=exc.message, id=exc.article_id)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(ArticleGenerationUpstreamError)
    async def handle_upstream_error(
        _request: Request, exc: ArticleGenerationUpstreamError
    ) -> JSONResponse:
        logger.warning("Article generation failed upstream: %s", exc.message)
        return _error_response(exc, status.HTTP_502_BAD_GATEWAY)

    @application.exception_handler(ArticleGenerationError)
    async def handle_generation_error(
        _request: Request, exc: ArticleGenerationError
    ) -> JSONResponse:
        logger.error("Article generation failed: %s", exc.message)
        return _error_response(exc, status.HTTP_500_INTERNAL_SERVER_ERROR)
