"""Unit tests for OpenAIWriter (no real OpenAI API calls)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import APIError

from app.config import Settings
from app.core.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIValidationError,
)
from app.schemas.ai import ArticleWriteInput
from app.services.ai.openai_writer import OpenAIWriter
from app.services.ai.prompt_loader import load_system_prompt


def _completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _settings(
    *,
    api_key: str = "test-key",
    model: str = "gpt-test",
    base_url: str | None = None,
    temperature: float = 0.4,
    max_tokens: int | None = 4000,
    target_word_count: int = 1800,
) -> Settings:
    return Settings(
        openai_api_key=api_key,
        openai_model=model,
        openai_base_url=base_url,
        openai_temperature=temperature,
        openai_max_tokens=max_tokens,
        article_target_word_count=target_word_count,
        database_url="postgresql+asyncpg://acf:acf_secret@localhost:5432/acf",
    )


@pytest.mark.asyncio
async def test_openai_writer_reads_model_from_settings() -> None:
    writer = OpenAIWriter(
        settings=_settings(model="gpt-configured"),
        client=AsyncMock(),
    )
    assert writer.model == "gpt-configured"
    assert writer.is_configured is True


@pytest.mark.asyncio
async def test_openai_writer_not_configured_without_api_key() -> None:
    writer = OpenAIWriter(settings=_settings(api_key=""), client=None)
    assert writer.is_configured is False
    with pytest.raises(AIConfigurationError, match="not configured"):
        await writer.generate(ArticleWriteInput(topic="Topic"))


@pytest.mark.asyncio
async def test_openai_writer_validates_json_response() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_completion(
            """
            {
              "title": "How to choose a pump",
              "meta_description": "A practical guide.",
              "content_markdown": "# How to choose a pump\\n\\nDetails.",
              "word_count": 6
            }
            """
        )
    )
    writer = OpenAIWriter(settings=_settings(), client=client)
    result = await writer.generate(
        ArticleWriteInput(topic="How to choose a pump", keywords=["pump"])
    )

    assert result.title == "How to choose a pump"
    assert result.word_count == 6
    client.chat.completions.create.assert_awaited_once()
    call_kwargs = client.chat.completions.create.await_args.kwargs
    assert call_kwargs["model"] == "gpt-test"
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert "How to choose a pump" in call_kwargs["messages"][1]["content"]


@pytest.mark.asyncio
async def test_openai_writer_applies_generation_settings() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_completion(
            '{"title": "T", "meta_description": "M",'
            ' "content_markdown": "# T", "word_count": 1}'
        )
    )
    writer = OpenAIWriter(
        settings=_settings(temperature=0.9, max_tokens=1234, target_word_count=900),
        client=client,
    )
    await writer.generate(ArticleWriteInput(topic="Topic"))

    call_kwargs = client.chat.completions.create.await_args.kwargs
    assert call_kwargs["temperature"] == 0.9
    assert call_kwargs["max_tokens"] == 1234
    assert "900" in call_kwargs["messages"][1]["content"]


@pytest.mark.asyncio
async def test_openai_writer_omits_max_tokens_when_unset() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_completion(
            '{"title": "T", "meta_description": "M",'
            ' "content_markdown": "# T", "word_count": 1}'
        )
    )
    writer = OpenAIWriter(settings=_settings(max_tokens=None), client=client)
    await writer.generate(ArticleWriteInput(topic="Topic"))

    assert "max_tokens" not in client.chat.completions.create.await_args.kwargs


@pytest.mark.asyncio
async def test_openai_writer_system_prompt_comes_from_file() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_completion(
            '{"title": "T", "meta_description": "M",'
            ' "content_markdown": "# T", "word_count": 1}'
        )
    )
    writer = OpenAIWriter(settings=_settings(), client=client)
    await writer.generate(ArticleWriteInput(topic="Topic"))

    system_message = client.chat.completions.create.await_args.kwargs["messages"][0]
    assert system_message["role"] == "system"
    assert system_message["content"] == load_system_prompt()


@pytest.mark.asyncio
async def test_openai_writer_rejects_invalid_json() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=_completion("not-json"))
    writer = OpenAIWriter(settings=_settings(), client=client)

    with pytest.raises(AIValidationError, match="validation"):
        await writer.generate(ArticleWriteInput(topic="Topic"))


@pytest.mark.asyncio
async def test_openai_writer_rejects_invalid_schema() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_completion('{"title": "Only title"}')
    )
    writer = OpenAIWriter(settings=_settings(), client=client)

    with pytest.raises(AIValidationError, match="validation"):
        await writer.generate(ArticleWriteInput(topic="Topic"))


@pytest.mark.asyncio
async def test_openai_writer_provider_errors_are_sanitized() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=APIError(
            message="secret key sk-secret leaked",
            request=None,
            body=None,
        )
    )
    writer = OpenAIWriter(settings=_settings(api_key="sk-secret"), client=client)

    with pytest.raises(AIProviderError) as exc_info:
        await writer.generate(ArticleWriteInput(topic="Topic"))

    message = str(exc_info.value)
    assert "sk-secret" not in message
    assert "stack" not in message.lower()
    assert "Article generation failed" in message


@pytest.mark.asyncio
async def test_openai_writer_init_does_not_call_api() -> None:
    client = AsyncMock()
    OpenAIWriter(settings=_settings(), client=client)
    client.chat.completions.create.assert_not_called()


def test_openai_writer_uses_default_endpoint_when_base_url_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_client(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "app.services.ai.openai_writer.AsyncOpenAI",
        fake_client,
    )
    writer = OpenAIWriter(settings=_settings())
    assert writer.base_url is None
    writer._get_client()
    assert "base_url" not in captured


def test_openai_writer_passes_custom_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_client(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "app.services.ai.openai_writer.AsyncOpenAI",
        fake_client,
    )
    writer = OpenAIWriter(
        settings=_settings(base_url="https://openrouter.ai/api/v1")
    )
    assert writer.base_url == "https://openrouter.ai/api/v1"
    writer._get_client()
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
