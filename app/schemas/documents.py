"""Request and response schemas for the knowledge-base API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.document import DocumentStatus
from app.schemas.rag import RetrievedChunk


class DocumentIngestRequest(BaseModel):
    """JSON body for POST /api/v1/documents."""

    model_config = ConfigDict(extra="forbid")

    title: str = ""
    content: str = Field(min_length=1)
    filename: str = ""
    content_type: str | None = None

    @field_validator("content")
    @classmethod
    def _require_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("title", "filename")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class DocumentResponse(BaseModel):
    """A stored knowledge-base document (without chunk vectors)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source: str
    content_type: str
    status: DocumentStatus
    chunk_count: int = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    """Document plus extracted text (used by GET by id)."""

    content_text: str = ""


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


class DocumentErrorResponse(BaseModel):
    """Sanitized ingest/search failure. Never contains secrets."""

    detail: str
    id: uuid.UUID | None = None
    status: DocumentStatus | None = None


class DocumentSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def _require_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class DocumentSearchResponse(BaseModel):
    query: str
    chunks: list[RetrievedChunk]


def document_response(document: object, chunk_count: int) -> DocumentResponse:
    """Map an ORM document to the list/ingest response without importing routes."""
    payload = DocumentResponse.model_validate(document)
    return payload.model_copy(update={"chunk_count": chunk_count})


def document_detail_response(
    document: object, chunk_count: int
) -> DocumentDetailResponse:
    payload = DocumentDetailResponse.model_validate(document)
    return payload.model_copy(update={"chunk_count": chunk_count})
