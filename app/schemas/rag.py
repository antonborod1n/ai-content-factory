"""Internal DTOs for RAG retrieval (not the HTTP ingest contract)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class RetrievedChunk(BaseModel):
    """One chunk returned from vector search."""

    model_config = ConfigDict(frozen=True)

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    chunk_index: int
    content: str
    score: float = Field(ge=0)


def format_knowledge_context(chunks: list[RetrievedChunk]) -> str:
    """Turn retrieved chunks into a prompt block. Empty list → empty string."""
    if not chunks:
        return ""
    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        title = chunk.document_title.strip() or "Untitled"
        parts.append(
            f"### Источник {index}: {title} (фрагмент {chunk.chunk_index + 1})\n"
            f"{chunk.content.strip()}"
        )
    return "\n\n".join(parts)
