"""Read the current project's topic queue. Does not generate articles."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ProjectDep
from app.core.project_paths import read_project_topics
from app.schemas.articles import ArticleGenerateRequest

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[ArticleGenerateRequest])
async def list_topics(project: ProjectDep) -> list[dict]:
    try:
        return read_project_topics(project.slug)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Topics file is not valid",
        ) from exc
