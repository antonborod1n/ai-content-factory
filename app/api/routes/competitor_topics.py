"""Competitor-inventory content plan endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.deps import CompetitorTopicsServiceDep
from app.api.uploads import read_upload
from app.schemas.competitor_topics import (
    CompetitorTopicsErrorResponse,
    CompetitorTopicsExportRequest,
    CompetitorTopicsExportResponse,
    CompetitorTopicsImportRequest,
    CompetitorTopicsListResponse,
    CompetitorTopicsResponse,
    CompetitorTopicsSourcesRequest,
    competitor_topics_response,
)

router = APIRouter(prefix="/competitor-topics", tags=["competitor-topics"])


@router.post(
    "",
    response_model=CompetitorTopicsResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Invalid content-plan JSON"},
        500: {
            "model": CompetitorTopicsErrorResponse,
            "description": "Import failed inside the application",
        },
    },
)
async def import_competitor_topics(
    payload: CompetitorTopicsImportRequest,
    service: CompetitorTopicsServiceDep,
) -> CompetitorTopicsResponse:
    """Map a competitor-topics content-plan JSON to article briefs."""
    plan = await service.import_plan(payload)
    return competitor_topics_response(plan)


@router.post(
    "/upload",
    response_model=CompetitorTopicsResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Empty or invalid JSON file"},
        500: {"model": CompetitorTopicsErrorResponse},
    },
)
async def upload_competitor_topics(
    service: CompetitorTopicsServiceDep,
    file: Annotated[UploadFile, File()],
) -> CompetitorTopicsResponse | JSONResponse:
    """Same as POST /competitor-topics, from a UTF-8 JSON file."""
    data = await read_upload(file)
    if not data:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Uploaded file is empty"},
        )
    try:
        payload = json.loads(data.decode("utf-8-sig"))
        request = CompetitorTopicsImportRequest.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "File is not valid UTF-8 JSON"},
        )
    except ValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exc.errors()},
        )
    plan = await service.import_plan(request)
    return competitor_topics_response(plan)


@router.post(
    "/sources",
    response_model=CompetitorTopicsResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Empty, unsupported, or unreadable competitor dump"},
        502: {"model": CompetitorTopicsErrorResponse},
        500: {"model": CompetitorTopicsErrorResponse},
    },
)
async def ingest_competitor_sources(
    service: CompetitorTopicsServiceDep,
    files: Annotated[list[UploadFile], File()],
    domain: Annotated[str, Form()] = "",
    niche: Annotated[str, Form()] = "",
    audience: Annotated[str, Form()] = "",
    geo: Annotated[str, Form()] = "",
    site_type: Annotated[str, Form()] = "",
    blog_format: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = "ru",
) -> CompetitorTopicsResponse:
    """Parse xlsx/csv/txt/json dumps, cluster via ContentGapAnalyst, persist briefs."""
    payloads: list[tuple[str, bytes]] = []
    for upload in files:
        payloads.append(
            (upload.filename or "competitor.csv", await read_upload(upload))
        )
    meta = CompetitorTopicsSourcesRequest(
        domain=domain,
        niche=niche,
        audience=audience,
        geo=geo,
        site_type=site_type,
        blog_format=blog_format,
        language=language,
    )
    plan = await service.ingest_sources(payloads, meta)
    return competitor_topics_response(plan)


@router.get("", response_model=CompetitorTopicsListResponse)
async def list_competitor_topics(
    service: CompetitorTopicsServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CompetitorTopicsListResponse:
    items, total = await service.list(limit=limit, offset=offset)
    return CompetitorTopicsListResponse(
        items=[competitor_topics_response(plan) for plan in items],
        total=total,
    )


@router.get(
    "/{plan_id}",
    response_model=CompetitorTopicsResponse,
    responses={404: {"model": CompetitorTopicsErrorResponse}},
)
async def get_competitor_topics(
    plan_id: uuid.UUID,
    service: CompetitorTopicsServiceDep,
) -> CompetitorTopicsResponse:
    plan = await service.get(plan_id)
    return competitor_topics_response(plan)


@router.post(
    "/{plan_id}/export",
    response_model=CompetitorTopicsExportResponse,
    responses={
        404: {"model": CompetitorTopicsErrorResponse},
        500: {"model": CompetitorTopicsErrorResponse},
    },
)
async def export_competitor_topics(
    plan_id: uuid.UUID,
    service: CompetitorTopicsServiceDep,
    payload: CompetitorTopicsExportRequest | None = None,
) -> CompetitorTopicsExportResponse:
    """Append unique briefs to topics.json. Does not generate articles."""
    path = payload.path if payload is not None else None
    return await service.export(plan_id, path=path)
