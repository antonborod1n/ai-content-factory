"""Knowledge-base document endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import DocumentServiceDep, RagServiceDep
from app.api.uploads import read_upload
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentErrorResponse,
    DocumentIngestRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    document_detail_response,
    document_response,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Invalid request body"},
        500: {
            "model": DocumentErrorResponse,
            "description": "Ingest failed inside the application",
        },
        502: {
            "model": DocumentErrorResponse,
            "description": "Embedding provider failed",
        },
    },
)
async def ingest_document(
    payload: DocumentIngestRequest,
    service: DocumentServiceDep,
) -> DocumentResponse:
    """Parse pasted text, chunk it, embed, and store in the knowledge base."""
    document, chunk_count = await service.ingest_text(
        content=payload.content,
        title=payload.title,
        filename=payload.filename,
        content_type=payload.content_type,
    )
    return document_response(document, chunk_count)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        413: {"description": "File is larger than MAX_UPLOAD_MB"},
        422: {"description": "Empty or unsupported file"},
        500: {"model": DocumentErrorResponse},
        502: {"model": DocumentErrorResponse},
    },
)
async def upload_document(
    service: DocumentServiceDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()] = "",
) -> DocumentResponse:
    """Ingest a .md / .txt / .pdf file into the knowledge base."""
    data = await read_upload(file)
    document, chunk_count = await service.ingest_file(
        data=data,
        filename=file.filename or "upload",
        title=title,
        content_type=file.content_type,
    )
    return document_response(document, chunk_count)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: DocumentServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DocumentListResponse:
    items, total = await service.list(limit=limit, offset=offset)
    return DocumentListResponse(
        items=[document_response(document, count) for document, count in items],
        total=total,
    )


@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    payload: DocumentSearchRequest,
    rag: RagServiceDep,
) -> DocumentSearchResponse:
    """Return the nearest knowledge-base chunks for a query."""
    chunks = await rag.search(payload.query, top_k=payload.top_k)
    return DocumentSearchResponse(query=payload.query, chunks=chunks)


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    responses={404: {"model": DocumentErrorResponse}},
)
async def get_document(
    document_id: uuid.UUID,
    service: DocumentServiceDep,
) -> DocumentDetailResponse:
    document, count = await service.get(document_id)
    return document_detail_response(document, count)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": DocumentErrorResponse}},
)
async def delete_document(
    document_id: uuid.UUID,
    service: DocumentServiceDep,
) -> None:
    await service.delete(document_id)
