"""Persistence for knowledge-base documents and chunks."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Chunk, Document, DocumentStatus
from app.db.models.project import DEFAULT_PROJECT_ID
from app.schemas.rag import RetrievedChunk


class DocumentRepository:
    """Database access for documents and their embedding chunks."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID | None = None,
    ) -> None:
        self._session = session
        self._project_id = project_id or DEFAULT_PROJECT_ID

    async def create(
        self,
        *,
        title: str,
        source: str = "",
        content_type: str = "text/markdown",
        content_text: str = "",
        status: DocumentStatus = DocumentStatus.PENDING,
        error_message: str | None = None,
    ) -> Document:
        document = Document(
            project_id=self._project_id,
            title=title,
            source=source,
            content_type=content_type,
            content_text=content_text,
            status=status,
            error_message=error_message,
        )
        self._session.add(document)
        await self._session.commit()
        await self._session.refresh(document)
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        document = await self._session.get(Document, document_id)
        if document is None or document.project_id != self._project_id:
            return None
        return document

    async def update(
        self, document_id: uuid.UUID, **fields: Any
    ) -> Document | None:
        document = await self.get_by_id(document_id)
        if document is None:
            return None
        for key, value in fields.items():
            if not hasattr(document, key):
                msg = f"Unknown document field: {key}"
                raise ValueError(msg)
            setattr(document, key, value)
        await self._session.commit()
        await self._session.refresh(document)
        return document

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[Document]:
        statement = (
            select(Document)
            .where(Document.project_id == self._project_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Document)
            .where(Document.project_id == self._project_id)
        )
        return int(result.scalar_one())

    async def chunk_count(self, document_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.document_id == document_id)
        )
        return int(result.scalar_one())

    async def replace_chunks(
        self,
        document_id: uuid.UUID,
        chunks: list[tuple[int, str, list[float]]],
    ) -> None:
        await self._session.execute(
            delete(Chunk).where(Chunk.document_id == document_id)
        )
        for index, content, embedding in chunks:
            self._session.add(
                Chunk(
                    document_id=document_id,
                    chunk_index=index,
                    content=content,
                    embedding=embedding,
                )
            )
        await self._session.commit()

    async def has_ready_chunks(self) -> bool:
        result = await self._session.execute(
            select(Chunk.id)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.project_id == self._project_id)
            .where(Document.status == DocumentStatus.READY)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def delete(self, document_id: uuid.UUID) -> bool:
        document = await self.get_by_id(document_id)
        if document is None:
            return False
        await self._session.delete(document)
        await self._session.commit()
        return True

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Nearest chunks by cosine distance (pgvector ``<=>``)."""
        distance = Chunk.embedding.cosine_distance(query_embedding)
        statement = (
            select(
                Chunk.id,
                Chunk.document_id,
                Document.title,
                Chunk.chunk_index,
                Chunk.content,
                distance.label("distance"),
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.project_id == self._project_id)
            .where(Document.status == DocumentStatus.READY)
            .order_by(distance)
            .limit(top_k)
        )
        result = await self._session.execute(statement)
        rows = result.all()
        retrieved: list[RetrievedChunk] = []
        for row in rows:
            distance_value = float(row.distance)
            retrieved.append(
                RetrievedChunk(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    document_title=row.title,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    score=max(0.0, 1.0 - distance_value),
                )
            )
        return retrieved
