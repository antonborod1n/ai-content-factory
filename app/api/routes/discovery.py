"""Topic Discovery endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import DiscoveryServiceDep
from app.schemas.discovery import (
    DiscoveryErrorResponse,
    DiscoveryExportRequest,
    DiscoveryExportResponse,
    DiscoveryListResponse,
    DiscoveryRequest,
    DiscoveryResponse,
    discovery_response,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post(
    "",
    response_model=DiscoveryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Invalid request body"},
        500: {
            "model": DiscoveryErrorResponse,
            "description": "Discovery failed inside the application",
        },
        502: {
            "model": DiscoveryErrorResponse,
            "description": "SERP or topic planner failed",
        },
    },
)
async def create_discovery(
    payload: DiscoveryRequest,
    service: DiscoveryServiceDep,
) -> DiscoveryResponse:
    """Build a content plan from Google / Yandex SERP snapshots."""
    plan = await service.discover(payload)
    return discovery_response(plan)


@router.get("", response_model=DiscoveryListResponse)
async def list_discovery(
    service: DiscoveryServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DiscoveryListResponse:
    items, total = await service.list(limit=limit, offset=offset)
    return DiscoveryListResponse(
        items=[discovery_response(plan) for plan in items],
        total=total,
    )


@router.get(
    "/{plan_id}",
    response_model=DiscoveryResponse,
    responses={404: {"model": DiscoveryErrorResponse}},
)
async def get_discovery(
    plan_id: uuid.UUID,
    service: DiscoveryServiceDep,
) -> DiscoveryResponse:
    plan = await service.get(plan_id)
    return discovery_response(plan)


@router.post(
    "/{plan_id}/export",
    response_model=DiscoveryExportResponse,
    responses={
        404: {"model": DiscoveryErrorResponse},
        500: {"model": DiscoveryErrorResponse},
    },
)
async def export_discovery(
    plan_id: uuid.UUID,
    service: DiscoveryServiceDep,
    payload: DiscoveryExportRequest | None = None,
) -> DiscoveryExportResponse:
    """Append unique briefs to topics.json. Does not generate articles."""
    path = payload.path if payload is not None else None
    return await service.export(plan_id, path=path)
