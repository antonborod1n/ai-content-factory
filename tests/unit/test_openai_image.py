"""OpenAIImageProvider with a fake Images API client."""

import base64
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.core.exceptions import AIProviderError, AIValidationError
from app.services.ai.mock_image import MINIMAL_PNG
from app.services.ai.openai_image import (
    OpenAIImageProvider,
    aspect_ratio_for_size,
    uses_openrouter_image_api,
)


def _openai_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://localhost/test",
        openai_image_model="gpt-image-1-mini",
        openai_base_url=None,
    )


class FakeImages:
    def __init__(self, *, b64: str | None = None, url: str | None = None) -> None:
        self._b64 = b64
        self._url = url
        self.kwargs: dict[str, Any] | None = None

    async def generate(self, **kwargs: Any) -> SimpleNamespace:
        self.kwargs = kwargs
        item = SimpleNamespace(b64_json=self._b64, url=self._url)
        return SimpleNamespace(data=[item])


class FakeClient:
    def __init__(self, images: FakeImages) -> None:
        self.images = images


class FakeHttp:
    def __init__(self, body: object, *, status_error: bool = False) -> None:
        self.body = body
        self.status_error = status_error
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def post(self, url: str, **kwargs: Any) -> SimpleNamespace:
        self.calls.append((url, kwargs.get("json")))
        if self.status_error:
            request = httpx.Request("POST", url)
            response = httpx.Response(502, request=request)
            raise httpx.HTTPStatusError("bad", request=request, response=response)

        def _json() -> object:
            return self.body

        return SimpleNamespace(json=_json, raise_for_status=lambda: None)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_image_provider_decodes_b64() -> None:
    encoded = base64.b64encode(MINIMAL_PNG).decode("ascii")
    images = FakeImages(b64=encoded)
    provider = OpenAIImageProvider(
        api_key="sk-test",
        client=FakeClient(images),
        settings=_openai_settings(),
    )
    payload = await provider.generate("mattress photo", kind="image")
    assert payload == MINIMAL_PNG
    assert images.kwargs is not None
    assert images.kwargs["response_format"] == "b64_json"


@pytest.mark.asyncio
async def test_image_provider_rejects_empty_payload() -> None:
    provider = OpenAIImageProvider(
        api_key="sk-test",
        client=FakeClient(FakeImages()),
        settings=_openai_settings(),
    )
    with pytest.raises(AIValidationError):
        await provider.generate("x", kind="image")


@pytest.mark.asyncio
async def test_openrouter_qwen_posts_to_images() -> None:
    encoded = base64.b64encode(MINIMAL_PNG).decode("ascii")
    http = FakeHttp({"data": [{"b64_json": encoded}]})
    images = FakeImages(b64="should-not-use")
    provider = OpenAIImageProvider(
        api_key="sk-test",
        model="qwen/qwen-image-3-pro",
        base_url="https://openrouter.ai/api/v1",
        size="1792x1024",
        http_client=http,  # type: ignore[arg-type]
        client=FakeClient(images),
    )
    payload = await provider.generate("mattress photo", kind="image")
    assert payload == MINIMAL_PNG
    assert images.kwargs is None
    assert http.calls[0][0] == "https://openrouter.ai/api/v1/images"
    assert http.calls[0][1] == {
        "model": "qwen/qwen-image-3-pro",
        "prompt": "mattress photo",
        "n": 1,
        "aspect_ratio": "16:9",
        "resolution": "1K",
    }


@pytest.mark.asyncio
async def test_openrouter_http_error_is_provider_error() -> None:
    provider = OpenAIImageProvider(
        api_key="sk-test",
        model="qwen/qwen-image-3-pro",
        base_url="https://openrouter.ai/api/v1",
        http_client=FakeHttp({}, status_error=True),  # type: ignore[arg-type]
    )
    with pytest.raises(AIProviderError):
        await provider.generate("x", kind="image")


def test_openrouter_routing_helpers() -> None:
    openrouter = "https://openrouter.ai/api/v1"
    assert uses_openrouter_image_api("qwen/qwen-image-3-pro", openrouter)
    assert uses_openrouter_image_api("x-ai/grok-imagine-image-2.0", openrouter)
    assert not uses_openrouter_image_api("openai/gpt-image-1-mini", openrouter)
    assert not uses_openrouter_image_api("gpt-image-2", openrouter)
    assert not uses_openrouter_image_api("qwen/qwen-image-3-pro", None)
    assert aspect_ratio_for_size("1024x1024") == "1:1"
    assert aspect_ratio_for_size("1792x1024") == "16:9"
    assert aspect_ratio_for_size("1536x1024") == "3:2"
