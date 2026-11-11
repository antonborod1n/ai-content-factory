"""Project catalog. Does not scope other resources by itself."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import ProjectRepositoryDep
from app.core.exceptions import ProjectNotFoundError, ProjectProtectedError
from app.core.project_paths import remove_project_files
from app.schemas.projects import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
    project_response,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    repository: ProjectRepositoryDep,
) -> list[ProjectResponse]:
    rows = await repository.list()
    return [project_response(row) for row in rows]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    body: ProjectCreateRequest,
    repository: ProjectRepositoryDep,
) -> ProjectResponse:
    existing = await repository.get_by_slug(body.slug)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project slug already exists",
        )
    project = await repository.create(
        name=body.name.strip(),
        slug=body.slug,
        domain=body.domain,
        language=body.language,
    )
    return project_response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdateRequest,
    repository: ProjectRepositoryDep,
) -> ProjectResponse:
    project = await repository.update(
        project_id,
        name=body.name,
        domain=body.domain,
        language=body.language,
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    repository: ProjectRepositoryDep,
) -> Response:
    try:
        slug = await repository.delete(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except ProjectProtectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    remove_project_files(slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    repository: ProjectRepositoryDep,
) -> ProjectResponse:
    project = await repository.get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project_response(project)
