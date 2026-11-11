"""OpenAIDzenWriter with a fake chat client."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.exceptions import AIValidationError
from app.schemas.dzen import DzenWriteInput
from app.services.ai.openai_dzen import OpenAIDzenWriter


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.kwargs = kwargs
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, content: str) -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def _input() -> DzenWriteInput:
    return DzenWriteInput(
        source_title="Как выбрать матрас",
        source_markdown="# Длинная статья",
        target_char_count=4000,
    )


@pytest.mark.asyncio
async def test_dzen_writer_parses_json() -> None:
    payload = {
        "title": "Как выбрать матрас",
        "content_markdown": (
            "![Главная](DZEN_COVER_PLACEHOLDER)\n\nКороткий текст."
        ),
        "char_count": 40,
    }
    writer = OpenAIDzenWriter(
        api_key="sk-test",
        client=FakeClient(json.dumps(payload)),
    )
    output = await writer.generate(_input())
    assert output.title == "Как выбрать матрас"
    assert "DZEN_COVER_PLACEHOLDER" in output.content_markdown


@pytest.mark.asyncio
async def test_dzen_writer_rejects_invalid_json() -> None:
    writer = OpenAIDzenWriter(api_key="sk-test", client=FakeClient("not-json"))
    with pytest.raises(AIValidationError):
        await writer.generate(_input())
