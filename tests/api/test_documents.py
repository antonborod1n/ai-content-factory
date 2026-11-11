"""API tests for knowledge-base document endpoints."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_embedder
from app.config import get_settings
from app.core.exceptions import AIProviderError
from app.db.models.document import DocumentStatus
from app.services.ai.mock_embedder import MockEmbedder

INGEST = "/api/v1/documents"


class FailingEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise AIProviderError("Embedding failed due to an AI provider error")


@pytest.mark.asyncio
async def test_ingest_document_returns_ready(
    api_app: FastAPI, client: AsyncClient
) -> None:
    response = await client.post(
        INGEST,
        json={
            "title": "Спека насоса",
            "filename": "pumps.md",
            "content": "# Насос\n\nВыбирайте промышленный насос по напору и подаче.",
        },
    )
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["status"] == DocumentStatus.READY.value
    assert body["title"] == "Спека насоса"
    assert body["chunk_count"] >= 1
    assert body["error_message"] is None


@pytest.mark.asyncio
async def test_ingest_rejects_blank_content(client: AsyncClient) -> None:
    response = await client.post(INGEST, json={"content": "  "})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_get_delete_document(client: AsyncClient) -> None:
    created = await client.post(
        INGEST,
        json={"title": "Doc", "content": "Промышленный насос для воды."},
    )
    doc_id = created.json()["id"]

    listed = await client.get(INGEST)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == doc_id

    detail = await client.get(f"{INGEST}/{doc_id}")
    assert detail.status_code == 200
    assert "Промышленный насос" in detail.json()["content_text"]

    deleted = await client.delete(f"{INGEST}/{doc_id}")
    assert deleted.status_code == 204

    missing = await client.get(f"{INGEST}/{doc_id}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_upload_markdown_file(client: AsyncClient) -> None:
    response = await client.post(
        f"{INGEST}/upload",
        files={
            "file": (
                "notes.md",
                b"# Notes\n\nPump head matters.",
                "text/markdown",
            )
        },
        data={"title": "Notes"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Notes"
    assert response.json()["status"] == DocumentStatus.READY.value


@pytest.mark.asyncio
async def test_upload_rejects_files_over_the_limit(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()

    response = await client.post(
        f"{INGEST}/upload",
        files={"file": ("big.md", b"a" * (1024 * 1024 + 1), "text/markdown")},
    )

    assert response.status_code == 413
    listed = await client.get(INGEST)
    assert listed.json()["total"] == 0


@pytest.mark.asyncio
async def test_search_returns_overlapping_chunk(client: AsyncClient) -> None:
    await client.post(
        INGEST,
        json={
            "title": "Спека",
            "content": "Промышленный насос подбирают по напору, подаче и NPSH.",
        },
    )
    response = await client.post(
        f"{INGEST}/search",
        json={"query": "промышленный насос напор"},
    )
    assert response.status_code == 200
    chunks = response.json()["chunks"]
    assert chunks
    assert "насос" in chunks[0]["content"].lower()


@pytest.mark.asyncio
async def test_ingest_returns_502_on_embedding_error(
    api_app: FastAPI, client: AsyncClient
) -> None:
    api_app.dependency_overrides[get_embedder] = lambda: FailingEmbedder()
    response = await client.post(
        INGEST,
        json={"content": "Промышленный насос и напор."},
    )
    assert response.status_code == 502
    body = response.json()
    assert body["detail"] == "Embedding failed due to an AI provider error"
    assert body["status"] == DocumentStatus.FAILED.value
    uuid.UUID(body["id"])


@pytest.mark.asyncio
async def test_get_unknown_document_is_404(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    response = await client.get(f"{INGEST}/{missing}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mock_embedder_is_used_by_default(api_app: FastAPI) -> None:
    embedder = api_app.dependency_overrides[get_embedder]()
    assert isinstance(embedder, MockEmbedder)
