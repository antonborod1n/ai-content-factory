"""JSON extraction and retry for chat replies (no real provider calls)."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.core.exceptions import AIValidationError
from app.schemas.ai import AISectionOutput
from app.schemas.pipeline import FactCheckOutput
from app.services.ai.openai_json import (
    OpenAIJsonCaller,
    extract_json_object,
    parse_model_json,
)


def _completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _caller(client: AsyncMock) -> OpenAIJsonCaller:
    settings = Settings(
        openai_api_key="test-key",
        database_url="postgresql+asyncpg://localhost/test",
    )
    return OpenAIJsonCaller(failure_label="Test", client=client, settings=settings)


@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Вот ответ:\n```json\n{"a": 1}\n```\nГотово.',
        'Ответ: {"a": 1} — конец.',
    ],
)
def test_extract_finds_the_object(raw: str) -> None:
    assert extract_json_object(raw) == {"a": 1}


def test_extract_keeps_fences_inside_json_strings() -> None:
    markdown = "## Код\n\n```python\nprint(1)\n```\n\nТекст."
    raw = json.dumps({"content_markdown": markdown}, ensure_ascii=False)

    assert extract_json_object(raw)["content_markdown"] == markdown


@pytest.mark.parametrize("raw", ['{"a": "обрезано', "[1, 2]", "", "просто текст"])
def test_extract_rejects_non_objects(raw: str) -> None:
    with pytest.raises(AIValidationError):
        extract_json_object(raw)


def test_parse_ignores_extra_keys_from_the_model() -> None:
    result = parse_model_json(
        '{"verdict": "ok", "issues": [], "reasoning": "всё сходится"}',
        FactCheckOutput,
    )
    assert result.verdict == "ok"


@pytest.mark.asyncio
async def test_complete_json_retries_once_after_an_invalid_reply() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _completion('{"content_markdown": "обрез'),
            _completion('{"content_markdown": "## Раздел"}'),
        ]
    )

    result = await _caller(client).complete_json("system", "user", AISectionOutput)

    assert result.content_markdown == "## Раздел"
    assert client.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_complete_json_gives_up_after_the_second_invalid_reply() -> None:
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=_completion("не json"))

    with pytest.raises(AIValidationError):
        await _caller(client).complete_json("system", "user", AISectionOutput)
    assert client.chat.completions.create.await_count == 2
