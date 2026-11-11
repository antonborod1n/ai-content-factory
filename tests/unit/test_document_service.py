"""Unit tests for DocumentService using in-memory doubles."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.core.exceptions import (
    AIProviderError,
    DocumentIngestUpstreamError,
    DocumentParseError,
)
from app.db.models.document import Document, DocumentStatus
from app.services.ai.mock_embedder import MockEmbedder
from app.services.document_service import DocumentService


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[uuid.UUID, Document] = {}
        self.chunks: dict[uuid.UUID, list[tuple[int, str, list[float]]]] = {}
        self.status_history: list[DocumentStatus] = []

    async def create(self, **fields: Any) -> Document:
        document = Document(id=uuid.uuid4(), **fields)
        self.documents[document.id] = document
        self.chunks[document.id] = []
        self.status_history.append(document.status)
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return self.documents.get(document_id)

    async def update(self, document_id: uuid.UUID, **fields: Any) -> Document | None:
        document = self.documents.get(document_id)
        if document is None:
            return None
        for key, value in fields.items():
            setattr(document, key, value)
        if "status" in fields:
            self.status_history.append(fields["status"])
        return document

    async def chunk_count(self, document_id: uuid.UUID) -> int:
        return len(self.chunks.get(document_id, []))

    async def replace_chunks(
        self,
        document_id: uuid.UUID,
        chunks: list[tuple[int, str, list[float]]],
    ) -> None:
        self.chunks[document_id] = list(chunks)

    async def delete(self, document_id: uuid.UUID) -> bool:
        if document_id not in self.documents:
            return False
        del self.documents[document_id]
        self.chunks.pop(document_id, None)
        return True

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[Document]:
        items = list(self.documents.values())
        return items[offset : offset + limit]

    async def list_with_chunk_counts(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[tuple[Document, int]]:
        items = list(self.documents.values())[offset : offset + limit]
        return [(doc, len(self.chunks.get(doc.id, []))) for doc in items]

    async def count(self) -> int:
        return len(self.documents)

    async def has_ready_chunks(self) -> bool:
        return any(
            doc.status is DocumentStatus.READY and self.chunks.get(doc.id)
            for doc in self.documents.values()
        )


@pytest.mark.asyncio
async def test_ingest_text_completes_with_chunks() -> None:
    repository = FakeDocumentRepository()
    service = DocumentService(
        repository,
        MockEmbedder(),
        chunk_size=80,
        chunk_overlap=10,
    )

    document, chunk_count = await service.ingest_text(
        content="# Насосы\n\n" + ("Выбирайте насос по напору. " * 8),
        title="Спека",
        filename="pumps.md",
    )

    assert document.status is DocumentStatus.READY
    assert document.title == "Спека"
    assert chunk_count >= 1
    assert repository.status_history[:3] == [
        DocumentStatus.PENDING,
        DocumentStatus.PROCESSING,
        DocumentStatus.READY,
    ]


@pytest.mark.asyncio
async def test_ingest_empty_content_fails_before_row() -> None:
    repository = FakeDocumentRepository()
    service = DocumentService(repository, MockEmbedder())
    with pytest.raises(DocumentParseError):
        await service.ingest_text(content="   ")
    assert repository.documents == {}


@pytest.mark.asyncio
async def test_ingest_marks_failed_on_embedding_error() -> None:
    class FailingEmbedder:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            raise AIProviderError("Embedding failed due to an AI provider error")

    repository = FakeDocumentRepository()
    service = DocumentService(repository, FailingEmbedder())

    with pytest.raises(DocumentIngestUpstreamError):
        await service.ingest_text(content="Промышленный насос и напор.")

    document = next(iter(repository.documents.values()))
    assert document.status is DocumentStatus.FAILED
    assert document.error_message == (
        "Embedding failed due to an AI provider error"
    )


@pytest.mark.asyncio
async def test_file_too_large_is_parse_error() -> None:
    repository = FakeDocumentRepository()
    service = DocumentService(
        repository, MockEmbedder(), max_file_bytes=10
    )
    with pytest.raises(DocumentParseError, match="too large"):
        await service.ingest_file(data=b"x" * 20, filename="a.md")
    assert repository.documents == {}
