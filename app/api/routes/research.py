"""Competitor research endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import ResearchServiceDep
from app.schemas.research import (
    ResearchErrorResponse,
    ResearchListResponse,
    ResearchRequest,
    ResearchResponse,
    research_response,
)

router = APIRouter(prefix="/research", tags=["research"])


@router.post(
    "",
    response_model=ResearchResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Invalid request body"},
        500: {
            "model": ResearchErrorResponse,
            "description": "Research failed inside the application",
        },
        502: {
            "model": ResearchErrorResponse,
            "description": "SERP or outline provider failed",
        },
    },
)
async def create_research(
    payload: ResearchRequest,
    service: ResearchServiceDep,
) -> ResearchResponse:
    """Search competitors, parse structure, store an improved outline."""
    run = await service.analyze(payload)
    return research_response(run, list(run.competitors))


@router.get("", response_model=ResearchListResponse)
async def list_research(
    service: ResearchServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ResearchListResponse:
    items, total = await service.list(limit=limit, offset=offset)
    return ResearchListResponse(
        items=[research_response(run, list(run.competitors)) for run in items],
        total=total,
    )


@router.get(
    "/{research_id}",
    response_model=ResearchResponse,
    responses={404: {"model": ResearchErrorResponse}},
)
async def get_research(
    research_id: uuid.UUID,
    service: ResearchServiceDep,
) -> ResearchResponse:
    run = await service.get(research_id)
    return research_response(run, list(run.competitors))
