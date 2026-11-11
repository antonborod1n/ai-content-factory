"""OpenAI-compatible embeddings client."""

from __future__ import annotations

import logging

from openai import APIError, AsyncOpenAI, OpenAIError

from app.config import Settings, get_settings
from app.core.embedding_const import EMBEDDING_DIMENSIONS
from app.core.exceptions import AIConfigurationError, AIProviderError, AIValidationError
from app.services.ai.openai_client import build_async_openai

logger = logging.getLogger(__name__)

_MAX_BATCH = 64


class OpenAIEmbedder:
    """Creates embeddings via the OpenAI embeddings API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
        client: AsyncOpenAI | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self._api_key = resolved.openai_api_key if api_key is None else api_key
        self._model = (
            resolved.openai_embedding_model if model is None else model
        )
        self._base_url = resolved.openai_base_url if base_url is None else base_url
        self._dimensions = (
            EMBEDDING_DIMENSIONS if dimensions is None else dimensions
        )
        self._timeout = resolved.openai_timeout_seconds
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def _get_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        if not self.is_configured:
            raise AIConfigurationError("OpenAI API key is not configured")
        self._client = build_async_openai(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _MAX_BATCH):
            batch = texts[start : start + _MAX_BATCH]
            vectors.extend(await self._embed_batch(client, batch))
        return vectors

    async def _embed_batch(
        self, client: AsyncOpenAI, batch: list[str]
    ) -> list[list[float]]:
        try:
            response = await client.embeddings.create(
                model=self._model,
                input=batch,
            )
        except AIConfigurationError:
            raise
        except (APIError, OpenAIError) as exc:
            logger.exception("OpenAI provider error during embedding")
            raise AIProviderError(
                "Embedding failed due to an AI provider error"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during embedding")
            raise AIProviderError(
                "Embedding failed due to an AI provider error"
            ) from exc

        try:
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors = [list(item.embedding) for item in ordered]
        except (AttributeError, TypeError) as exc:
            raise AIValidationError(
                "Embedding response failed validation"
            ) from exc

        if len(vectors) != len(batch):
            raise AIValidationError("Embedding response failed validation")
        for vector in vectors:
            if len(vector) != self._dimensions:
                raise AIValidationError("Embedding response failed validation")
        return vectors
