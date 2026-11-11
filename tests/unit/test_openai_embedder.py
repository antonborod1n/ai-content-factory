"""Unit tests for OpenAIEmbedder (no real API calls)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import APIError

from app.config import Settings
from app.core.embedding_const import EMBEDDING_DIMENSIONS
from app.core.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIValidationError,
)
from app.services.ai.openai_embedder import OpenAIEmbedder


def _settings(*, api_key: str = "test-key") -> Settings:
    return Settings(
        openai_api_key=api_key,
        database_url="postgresql+asyncpg://localhost/test",
    )


def _embedding_response(vectors: list[list[float]]) -> SimpleNamespace:
    data = [
        SimpleNamespace(index=index, embedding=vector)
        for index, vector in enumerate(vectors)
    ]
    return SimpleNamespace(data=data)


@pytest.mark.asyncio
async def test_not_configured_without_api_key() -> None:
    embedder = OpenAIEmbedder(settings=_settings(api_key=""), client=None)
    assert embedder.is_configured is False
    with pytest.raises(AIConfigurationError, match="not configured"):
        await embedder.embed(["hello"])


@pytest.mark.asyncio
async def test_embed_returns_ordered_vectors() -> None:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[0] = 1.0
    client = AsyncMock()
    client.embeddings.create = AsyncMock(return_value=_embedding_response([vector]))
    embedder = OpenAIEmbedder(settings=_settings(), client=client)

    result = await embedder.embed(["насос"])

    assert result == [vector]
    client.embeddings.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_wrong_dimension_is_validation_error() -> None:
    client = AsyncMock()
    client.embeddings.create = AsyncMock(
        return_value=_embedding_response([[0.1, 0.2]])
    )
    embedder = OpenAIEmbedder(settings=_settings(), client=client)
    with pytest.raises(AIValidationError):
        await embedder.embed(["насос"])


@pytest.mark.asyncio
async def test_provider_error_is_sanitized() -> None:
    client = AsyncMock()
    client.embeddings.create = AsyncMock(
        side_effect=APIError(
            message="secret-key-leaked",
            request=None,
            body=None,
        )
    )
    embedder = OpenAIEmbedder(settings=_settings(), client=client)
    with pytest.raises(AIProviderError, match="Embedding failed"):
        await embedder.embed(["насос"])
