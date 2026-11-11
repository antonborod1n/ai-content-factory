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
    # Off by default so each test controls how many provider calls it expects.
    expand_attempts: int = 0,
    min_word_ratio: float = 0.8,
) -> Settings:
    return Settings(
        openai_api_key=api_key,
        openai_model=model,
        openai_base_url=base_url,
        openai_temperature=temperature,
        openai_max_tokens=max_tokens,
        article_target_word_count=target_word_count,
        article_expand_attempts=expand_attempts,
        article_min_word_ratio=min_word_ratio,
        database_url="postgresql+asyncpg://localhost/test",
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


def _article_json(words: int, *, title: str = "T") -> str:
    body = " ".join(["слово"] * words)
    return (
        f'{{"title": "{title}", "meta_description": "M",'
        f' "content_markdown": "# {title}\\n\\n{body}", "word_count": {words}}}'
    )


@pytest.mark.asyncio
async def test_openai_writer_expands_a_draft_below_the_target() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _completion(_article_json(20, title="Short")),
            _completion(_article_json(200, title="Long")),
        ]
    )
    writer = OpenAIWriter(
        settings=_settings(target_word_count=200, expand_attempts=2),
        client=client,
    )

    result = await writer.generate(ArticleWriteInput(topic="Тема"))

    assert result.title == "Long"
    assert client.chat.completions.create.await_count == 2
    expand_prompt = client.chat.completions.create.await_args_list[1].kwargs[
        "messages"
    ][1]["content"]
    # The second call must carry the first draft, not start from scratch.
    assert "# Short" in expand_prompt


@pytest.mark.asyncio
async def test_openai_writer_keeps_a_long_enough_draft() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_completion(_article_json(200))
    )
    writer = OpenAIWriter(
        settings=_settings(target_word_count=200, expand_attempts=2),
        client=client,
    )

    await writer.generate(ArticleWriteInput(topic="Тема"))

    client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_writer_stops_expanding_when_it_does_not_grow() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_completion(_article_json(20))
    )
    writer = OpenAIWriter(
        settings=_settings(target_word_count=200, expand_attempts=3),
        client=client,
    )

    result = await writer.generate(ArticleWriteInput(topic="Тема"))

    assert result.word_count == 20
    assert client.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_openai_writer_returns_the_draft_when_expansion_fails() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _completion(_article_json(20, title="Draft")),
            APIError(message="provider is down", request=None, body=None),
        ]
    )
    writer = OpenAIWriter(
        settings=_settings(target_word_count=200, expand_attempts=2),
        client=client,
    )

    result = await writer.generate(ArticleWriteInput(topic="Тема"))

    assert result.title == "Draft"


@pytest.mark.asyncio
async def test_openai_writer_writes_long_articles_section_by_section() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _completion(
                '{"title": "Матрасы", "meta_description": "Описание",'
                ' "url_slug": "matrasy"}'
            ),
            _completion('{"content_markdown": "## **Первый**\\n\\nТекст."}'),
            _completion('{"content_markdown": "## **Второй**\\n\\nЕщё текст."}'),
        ]
    )
    writer = OpenAIWriter(settings=_settings(), client=client)

    result = await writer.generate(
        ArticleWriteInput(topic="Матрасы", outline=["Первый", "Второй"])
    )

    assert client.chat.completions.create.await_count == 3
    assert result.title == "Матрасы"
    assert result.url_slug == "matrasy"
    assert result.content_markdown == (
        "# **Матрасы**\n\n## **Первый**\n\nТекст.\n\n## **Второй**\n\nЕщё текст."
    )
    assert result.word_count == 6

    second_section_prompt = client.chat.completions.create.await_args_list[
        2
    ].kwargs["messages"][1]["content"]
    # Later sections must know what was already covered.
    assert "Первый" in second_section_prompt


_META_JSON = (
    '{"title": "Матрасы", "meta_description": "Описание", "url_slug": "matrasy"}'
)


def _section_json(heading: str, words: int) -> str:
    body = " ".join(["слово"] * words)
    return f'{{"content_markdown": "## **{heading}**\\n\\n{body}"}}'


@pytest.mark.asyncio
async def test_openai_writer_expands_a_short_section() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _completion(_META_JSON),
            _completion(_section_json("Первый", 5)),
            _completion(_section_json("Первый", 200)),
            _completion(_section_json("Второй", 200)),
        ]
    )
    # 400 words over two sections: each must reach 80% of 200.
    writer = OpenAIWriter(
        settings=_settings(target_word_count=400, expand_attempts=2),
        client=client,
    )

    result = await writer.generate(
        ArticleWriteInput(topic="Матрасы", outline=["Первый", "Второй"])
    )

    assert client.chat.completions.create.await_count == 4
    assert result.word_count == 1 + 201 + 201
    retry_prompt = client.chat.completions.create.await_args_list[2].kwargs[
        "messages"
    ][1]["content"]
    assert "Доработка раздела" in retry_prompt
    assert "## **Первый**\n\nслово слово слово слово слово" in retry_prompt


@pytest.mark.asyncio
async def test_openai_writer_keeps_a_section_when_its_expansion_fails() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _completion(_META_JSON),
            _completion(_section_json("Первый", 5)),
            APIError(message="provider is down", request=None, body=None),
            _completion(_section_json("Второй", 200)),
        ]
    )
    writer = OpenAIWriter(
        settings=_settings(target_word_count=400, expand_attempts=2),
        client=client,
    )

    result = await writer.generate(
        ArticleWriteInput(topic="Матрасы", outline=["Первый", "Второй"])
    )

    assert "## **Первый**\n\nслово слово слово слово слово\n\n" in (
        result.content_markdown
    )
    assert result.word_count == 1 + 6 + 201


@pytest.mark.asyncio
async def test_openai_writer_uses_one_call_without_an_outline() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_completion(_article_json(200))
    )
    writer = OpenAIWriter(
        settings=_settings(target_word_count=200), client=client
    )

    await writer.generate(ArticleWriteInput(topic="Тема"))

    client.chat.completions.create.assert_awaited_once()


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
        "app.services.ai.openai_client.AsyncOpenAI",
        fake_client,
    )
    writer = OpenAIWriter(settings=_settings())
    assert writer.base_url is None
    writer._get_client()
    assert "base_url" not in captured
    assert captured["timeout"] == 300.0
    assert captured["max_retries"] == 1


def test_openai_writer_passes_custom_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_client(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "app.services.ai.openai_client.AsyncOpenAI",
        fake_client,
    )
    writer = OpenAIWriter(
        settings=_settings(base_url="https://openrouter.ai/api/v1")
    )
    assert writer.base_url == "https://openrouter.ai/api/v1"
    writer._get_client()
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
