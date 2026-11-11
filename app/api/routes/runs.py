"""Read-only history of article, image, and competitor runs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import RunServiceDep
from app.core.exceptions import RunNotFoundError
from app.schemas.runs import RunListResponse, RunResponse, run_response

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=RunListResponse)
async def list_runs(
    service: RunServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    task_type: str | None = Query(default=None, max_length=40),
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
) -> RunListResponse:
    items, total = await service.list(
        limit=limit,
        offset=offset,
        task_type=task_type,
        status=status_filter,
    )
    return RunListResponse(items=[run_response(item) for item in items], total=total)


@router.get("/active", response_model=RunListResponse)
async def list_active_runs(service: RunServiceDep) -> RunListResponse:
    items = await service.list_active()
    return RunListResponse(
        items=[run_response(item) for item in items], total=len(items)
    )


@router.get(
    "/{run_id}",
    response_model=RunResponse,
    responses={404: {"description": "Run not found"}},
)
async def get_run(run_id: uuid.UUID, service: RunServiceDep) -> RunResponse:
    try:
        run = await service.get(run_id)
    except RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from None
    return run_response(run)
