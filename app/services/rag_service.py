"""Retrieve knowledge-base chunks for a query or article brief."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.ai import ArticleWriteInput
from app.schemas.rag import RetrievedChunk, format_knowledge_context
from app.services.ai.embedder import Embedder

logger = logging.getLogger(__name__)


class RagService:
    """Vector search + prompt-context formatting. No HTTP, no SQL strings."""

    def __init__(
        self,
        repository: DocumentRepository,
        embedder: Embedder,
        *,
        top_k: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        settings = get_settings()
        self._repository = repository
        self._embedder = embedder
        self._top_k = settings.rag_top_k if top_k is None else top_k
        self._enabled = settings.rag_enabled if enabled is None else enabled

    async def search(
        self, query: str, *, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        cleaned = query.strip()
        if not cleaned:
            return []
        if not await self._repository.has_ready_chunks():
            return []
        limit = self._top_k if top_k is None else top_k
        vectors = await self._embedder.embed([cleaned])
        return await self._repository.search_similar(vectors[0], top_k=limit)

    async def context_for_article(self, request: ArticleWriteInput) -> str:
        """Empty string when RAG is off, disabled on the request, or KB is empty."""
        if not self._enabled or not request.use_knowledge_base:
            return ""
        query = _query_from_request(request)
        chunks = await self.search(query)
        if chunks:
            logger.info(
                "RAG retrieved %s chunks for topic=%s",
                len(chunks),
                request.topic,
            )
        return format_knowledge_context(chunks)


def _query_from_request(request: ArticleWriteInput) -> str:
    parts = [request.topic, *request.primary_keywords, *request.keywords]
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        cleaned = part.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return " ".join(unique)
