"""Article generation endpoints."""

from fastapi import APIRouter, status

from app.api.deps import ArticleServiceDep
from app.schemas.articles import (
    ArticleErrorResponse,
    ArticleGenerateRequest,
    ArticleGenerateResponse,
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
    return ArticleGenerateResponse.model_validate(article)
