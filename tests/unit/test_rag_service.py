"""Unit tests for RagService."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.ai import ArticleWriteInput
from app.schemas.rag import RetrievedChunk, format_knowledge_context
from app.services.ai.mock_embedder import MockEmbedder
from app.services.rag_service import RagService


class FakeSearchRepository:
    def __init__(
        self, chunks: list[RetrievedChunk], *, has_chunks: bool = True
    ) -> None:
        self.chunks = chunks
        self.has_chunks = has_chunks
        self.queries: list[list[float]] = []

    async def has_ready_chunks(self) -> bool:
        return self.has_chunks

    async def search_similar(
        self, query_embedding: list[float], *, top_k: int = 5
    ) -> list[RetrievedChunk]:
        self.queries.append(query_embedding)
        return self.chunks[:top_k]


def _chunk(content: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Спека насоса",
        chunk_index=0,
        content=content,
        score=0.9,
    )


def test_format_knowledge_context_empty() -> None:
    assert format_knowledge_context([]) == ""


def test_format_knowledge_context_includes_title() -> None:
    rendered = format_knowledge_context([_chunk("Рабочее давление 10 бар.")])
    assert "Спека насоса" in rendered
    assert "10 бар" in rendered


@pytest.mark.asyncio
async def test_search_skips_embedder_when_kb_empty() -> None:
    class ExplodingEmbedder:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            raise AssertionError("embed must not be called")

    rag = RagService(FakeSearchRepository([], has_chunks=False), ExplodingEmbedder())
    assert await rag.search("насос") == []


@pytest.mark.asyncio
async def test_context_for_article_uses_topic() -> None:
    chunk = _chunk("Выбирайте насос по напору.")
    repo = FakeSearchRepository([chunk])
    rag = RagService(repo, MockEmbedder(), top_k=3, enabled=True)
    context = await rag.context_for_article(
        ArticleWriteInput(topic="Как выбрать насос", keywords=["напор"])
    )
    assert "Выбирайте насос по напору" in context
    assert repo.queries


@pytest.mark.asyncio
async def test_context_for_article_can_be_disabled() -> None:
    rag = RagService(
        FakeSearchRepository([_chunk("secret")]),
        MockEmbedder(),
        enabled=True,
    )
    context = await rag.context_for_article(
        ArticleWriteInput(topic="Насос", use_knowledge_base=False)
    )
    assert context == ""
