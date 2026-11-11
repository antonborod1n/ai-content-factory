"""Article generation and catalog endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.deps import ArticleServiceDep
from app.core.exceptions import ArticleNotFoundError
from app.schemas.articles import (
    ArticleErrorResponse,
    ArticleGenerateRequest,
    ArticleGenerateResponse,
    ArticleListResponse,
    ArticleReviewRequest,
    ArticleStatus,
    ReviewStatus,
    article_detail_response,
    article_list_item,
)

router = APIRouter(prefix="/articles", tags=["articles"])


@router.post(
    "/generate",
    response_model=ArticleGenerateResponse,
    status_code=status.HTTP_200_OK,
    responses={
        422: {"description": "Invalid request body"},
        500: {
            "model": ArticleErrorResponse,
            "description": "Generation failed inside the application",
        },
        502: {
            "model": ArticleErrorResponse,
            "description": "AI provider failed or returned an invalid response",
        },
    },
)
async def generate_article(
    payload: ArticleGenerateRequest,
    service: ArticleServiceDep,
) -> ArticleGenerateResponse:
    """Generate an article and store it.

    Failures are translated to sanitized error responses by the application
    exception handlers.
    """
    article = await service.generate(payload.to_write_input())
    return article_detail_response(article)


@router.get("", response_model=ArticleListResponse)
async def list_articles(
    service: ArticleServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    article_status: Annotated[
        ArticleStatus | None,
        Query(alias="status"),
    ] = None,
    review_status: Annotated[ReviewStatus | None, Query()] = None,
) -> ArticleListResponse:
    items, total = await service.list(
        limit=limit,
        offset=offset,
        status=article_status,
        review_status=review_status,
    )
    return ArticleListResponse(
        items=[article_list_item(article) for article in items],
        total=total,
    )


@router.get(
    "/{article_id}",
    response_model=ArticleGenerateResponse,
    responses={
        404: {
            "model": ArticleErrorResponse,
            "description": "Article not found",
        },
    },
)
async def get_article(
    article_id: uuid.UUID,
    service: ArticleServiceDep,
) -> ArticleGenerateResponse:
    article = await service.get(article_id)
    return article_detail_response(article)


@router.patch(
    "/{article_id}/review",
    response_model=ArticleGenerateResponse,
    responses={
        404: {
            "model": ArticleErrorResponse,
            "description": "Article not found",
        },
    },
)
async def review_article(
    article_id: uuid.UUID,
    payload: ArticleReviewRequest,
    service: ArticleServiceDep,
) -> ArticleGenerateResponse:
    """Store the operator verdict. Does not publish to a CMS."""
    article = await service.set_review(article_id, payload.review_status)
    return article_detail_response(article)


@router.post(
    "/{article_id}/images",
    response_model=ArticleGenerateResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {
            "model": ArticleErrorResponse,
            "description": "Article not found",
        },
        500: {
            "model": ArticleErrorResponse,
            "description": "Image generation failed inside the application",
        },
    },
)
async def regenerate_article_images(
    article_id: uuid.UUID,
    service: ArticleServiceDep,
) -> ArticleGenerateResponse:
    """Generate or replace images for an existing article. Text is unchanged."""
    article = await service.regenerate_images(article_id)
    return article_detail_response(article)


@router.get(
    "/{article_id}/media/{file_path:path}",
    responses={
        404: {"description": "Article or media file not found"},
    },
)
async def get_article_media(
    article_id: uuid.UUID,
    file_path: str,
    service: ArticleServiceDep,
) -> FileResponse:
    """Serve a generated image from the article output folder."""
    try:
        path = await service.resolve_media(article_id, file_path)
    except ArticleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found",
        )
    return FileResponse(path)
