"""Knowledge-base ingest orchestration."""

from __future__ import annotations

import logging
import uuid

from app.config import get_settings
from app.core.chunking import chunk_text
from app.core.document_parser import (
    ParsedDocument,
    parse_binary_document,
    parse_text_document,
)
from app.core.exceptions import (
    AIConfigurationError,
    AIError,
    DocumentIngestError,
    DocumentIngestUpstreamError,
    DocumentNotFoundError,
    DocumentParseError,
)
from app.db.models.document import Document, DocumentStatus
from app.repositories.document_repository import DocumentRepository
from app.services.ai.embedder import Embedder
from app.services.run_tracker import RunTracker

logger = logging.getLogger(__name__)

_GENERIC_FAILURE = "Document ingest failed"


class DocumentService:
    """Parse → chunk → embed → persist. Status transitions stay in this service."""

    def __init__(
        self,
        repository: DocumentRepository,
        embedder: Embedder,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        max_file_bytes: int | None = None,
        run_tracker: RunTracker | None = None,
    ) -> None:
        settings = get_settings()
        self._repository = repository
        self._embedder = embedder
        self._chunk_size = (
            settings.rag_chunk_size if chunk_size is None else chunk_size
        )
        self._chunk_overlap = (
            settings.rag_chunk_overlap if chunk_overlap is None else chunk_overlap
        )
        self._max_file_bytes = (
            settings.rag_max_file_bytes
            if max_file_bytes is None
            else max_file_bytes
        )
        self._runs = run_tracker or RunTracker()

    async def ingest_text(
        self,
        *,
        content: str,
        title: str = "",
        filename: str = "",
        content_type: str | None = None,
    ) -> tuple[Document, int]:
        parsed = parse_text_document(
            content=content,
            title=title,
            filename=filename,
            content_type=content_type,
        )
        return await self._ingest_parsed(parsed)

    async def ingest_file(
        self,
        *,
        data: bytes,
        filename: str,
        title: str = "",
        content_type: str | None = None,
    ) -> tuple[Document, int]:
        if len(data) > self._max_file_bytes:
            raise DocumentParseError("Uploaded file is too large")
        parsed = parse_binary_document(
            data=data,
            filename=filename,
            title=title,
            content_type=content_type,
        )
        return await self._ingest_parsed(parsed)

    async def get(self, document_id: uuid.UUID) -> tuple[Document, int]:
        document = await self._repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        count = await self._repository.chunk_count(document_id)
        return document, count

    async def list(
        self, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[tuple[Document, int]], int]:
        items = await self._repository.list_with_chunk_counts(
            limit=limit, offset=offset
        )
        total = await self._repository.count()
        return items, total

    async def delete(self, document_id: uuid.UUID) -> None:
        document = await self._repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        deleted = await self._repository.delete(document_id)
        if not deleted:
            raise DocumentNotFoundError(document_id)
        run_id = await self._runs.start(
            "document_delete",
            {"document_id": str(document_id), "title": document.title},
        )
        await self._runs.finish(
            run_id,
            status="completed",
            output_json={"document_id": str(document_id)},
            error=None,
        )

    async def _ingest_parsed(self, parsed: ParsedDocument) -> tuple[Document, int]:
        document = await self._repository.create(
            title=parsed.title,
            source=parsed.source,
            content_type=parsed.content_type,
            content_text=parsed.text,
            status=DocumentStatus.PENDING,
        )
        await self._repository.update(
            document.id, status=DocumentStatus.PROCESSING
        )
        logger.info(
            "Ingesting document id=%s title=%s chars=%s",
            document.id,
            parsed.title,
            len(parsed.text),
        )
        run_id = await self._runs.start(
            "document",
            {
                "document_id": str(document.id),
                "title": parsed.title,
                "source": parsed.source,
            },
        )
        history_output: dict[str, object] | None = None
        try:
            await self._embed_document(document.id, parsed.text)
            ready = await self._repository.update(
                document.id,
                status=DocumentStatus.READY,
                error_message=None,
            )
            if ready is None:
                raise DocumentIngestError(_GENERIC_FAILURE, document_id=document.id)
            count = await self._repository.chunk_count(ready.id)
            logger.info(
                "Document ready id=%s chunks=%s",
                ready.id,
                count,
            )
            history_output = {
                "document_id": str(ready.id),
                "title": ready.title,
                "chunks": count,
            }
            return ready, count
        finally:
            await self._runs.finish_current(run_id, output_json=history_output)

    async def _embed_document(self, document_id: uuid.UUID, text: str) -> int:
        try:
            pieces = chunk_text(
                text,
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
            )
            if not pieces:
                raise DocumentParseError("Document content is empty")
            vectors = await self._embedder.embed(pieces)
            if len(vectors) != len(pieces):
                raise DocumentIngestError(_GENERIC_FAILURE, document_id=document_id)
            await self._repository.replace_chunks(
                document_id,
                list(zip(range(len(pieces)), pieces, vectors, strict=True)),
            )
            return len(pieces)
        except DocumentParseError as exc:
            await self._mark_failed(document_id, exc.message)
            raise DocumentIngestError(
                exc.message, document_id=document_id
            ) from exc
        except AIConfigurationError as exc:
            logger.exception("Embedding provider is not configured")
            await self._mark_failed(document_id, _GENERIC_FAILURE)
            raise DocumentIngestError(
                _GENERIC_FAILURE, document_id=document_id
            ) from exc
        except AIError as exc:
            await self._mark_failed(document_id, exc.message)
            raise DocumentIngestUpstreamError(
                exc.message, document_id=document_id
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error while ingesting document")
            await self._mark_failed(document_id, _GENERIC_FAILURE)
            raise DocumentIngestError(
                _GENERIC_FAILURE, document_id=document_id
            ) from exc

    async def _mark_failed(self, document_id: uuid.UUID, message: str) -> None:
        try:
            await self._repository.update(
                document_id,
                status=DocumentStatus.FAILED,
                error_message=message,
            )
        except Exception:
            logger.exception("Could not mark document %s as failed", document_id)
