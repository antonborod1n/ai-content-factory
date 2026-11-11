"""OpenAI-backed ImageProvider (Images API + OpenRouter /images)."""

from __future__ import annotations

import base64
import logging
from types import SimpleNamespace

import httpx
from openai import APIError, AsyncOpenAI, OpenAIError

from app.config import Settings, get_settings
from app.core.exceptions import AIConfigurationError, AIProviderError, AIValidationError
from app.services.ai.openai_client import build_async_openai

logger = logging.getLogger(__name__)

_OPENROUTER_IMAGE_TIMEOUT = 180.0
_SIZE_TO_ASPECT = {
    "1024x1024": "1:1",
    "1024x1536": "2:3",
    "1536x1024": "3:2",
    "1024x1792": "9:16",
    "1792x1024": "16:9",
}


class OpenAIImageProvider:
    """Generates images via OpenAI Images or OpenRouter Image API. No call on init."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        size: str | None = None,
        client: AsyncOpenAI | None = None,
        http_client: httpx.AsyncClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self._api_key = resolved.openai_api_key if api_key is None else api_key
        self._model = (
            resolved.openai_image_model if model is None else model
        )
        self._base_url = resolved.openai_base_url if base_url is None else base_url
        self._size = resolved.openai_image_size if size is None else size
        self._timeout = resolved.openai_timeout_seconds
        self._client = client
        self._http_client = http_client

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

    async def generate(self, prompt: str, *, kind: str) -> bytes:
        if uses_openrouter_image_api(self._model, self._base_url):
            return await self._generate_openrouter(prompt, kind=kind)
        return await self._generate_openai(prompt, kind=kind)

    async def _generate_openai(self, prompt: str, *, kind: str) -> bytes:
        client = self._get_client()
        try:
            response = await client.images.generate(
                model=self._model,
                prompt=prompt,
                size=self._size,
                n=1,
                response_format="b64_json",
            )
        except AIConfigurationError:
            raise
        except (APIError, OpenAIError) as exc:
            logger.exception("OpenAI provider error during %s generation", kind)
            raise AIProviderError(
                "Image generation failed due to an AI provider error"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during %s generation", kind)
            raise AIProviderError(
                "Image generation failed due to an AI provider error"
            ) from exc

        return await self._bytes_from_response(response)

    async def _generate_openrouter(self, prompt: str, *, kind: str) -> bytes:
        if not self.is_configured:
            raise AIConfigurationError("OpenAI API key is not configured")
        url = f"{str(self._base_url).rstrip('/')}/images"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": aspect_ratio_for_size(self._size),
            "resolution": "1K",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        client = self._http_client or httpx.AsyncClient(
            timeout=_OPENROUTER_IMAGE_TIMEOUT
        )
        owns = self._http_client is None
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        except AIConfigurationError:
            raise
        except httpx.HTTPError as exc:
            logger.exception("OpenRouter image error during %s generation", kind)
            raise AIProviderError(
                "Image generation failed due to an AI provider error"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during %s generation", kind)
            raise AIProviderError(
                "Image generation failed due to an AI provider error"
            ) from exc
        finally:
            if owns:
                await client.aclose()
        return await self._bytes_from_response(_response_from_json(body))

    async def _bytes_from_response(self, response: object) -> bytes:
        try:
            item = response.data[0]
        except (AttributeError, IndexError, TypeError) as exc:
            raise AIValidationError("AI response failed validation") from exc

        b64 = getattr(item, "b64_json", None)
        if b64:
            try:
                return base64.b64decode(b64)
            except (ValueError, TypeError) as exc:
                raise AIValidationError("AI response failed validation") from exc

        url = getattr(item, "url", None)
        if url and str(url).strip():
            return await self._download(str(url))
        raise AIValidationError("AI response failed validation")

    async def _download(self, url: str) -> bytes:
        client = self._http_client or httpx.AsyncClient(timeout=30.0)
        owns = self._http_client is None
        try:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.content
        except httpx.HTTPError as exc:
            raise AIProviderError(
                "Image generation failed due to an AI provider error"
            ) from exc
        finally:
            if owns:
                await client.aclose()
        if not payload:
            raise AIValidationError("AI response failed validation")
        return payload


def uses_openrouter_image_api(model: str, base_url: str | None) -> bool:
    """Qwen and other dedicated OpenRouter image models use POST /images."""
    if not base_url or "openrouter.ai" not in base_url.lower():
        return False
    cleaned = (model or "").strip().lower()
    if cleaned.startswith("openai/") or cleaned.startswith("dall-e"):
        return False
    if cleaned.startswith("gpt-image"):
        return False
    return bool(cleaned)


def aspect_ratio_for_size(size: str) -> str:
    """Map OpenAI-style WxH to an OpenRouter aspect_ratio."""
    return _SIZE_TO_ASPECT.get((size or "").strip(), "1:1")


def _response_from_json(body: object) -> SimpleNamespace:
    if not isinstance(body, dict):
        raise AIValidationError("AI response failed validation")
    raw = body.get("data")
    if not isinstance(raw, list) or not raw:
        raise AIValidationError("AI response failed validation")
    first = raw[0]
    if not isinstance(first, dict):
        raise AIValidationError("AI response failed validation")
    return SimpleNamespace(
        data=[
            SimpleNamespace(
                b64_json=first.get("b64_json"),
                url=first.get("url"),
            )
        ]
    )
