"""OpenAI quality agents with a fake chat client."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.exceptions import AIValidationError
from app.schemas.quality import DetectorInput, HumanizerInput, SummaryInput
from app.services.ai.openai_detector import OpenAIDetector
from app.services.ai.openai_humanizer import OpenAIHumanizer
from app.services.ai.openai_summarizer import OpenAISummarizer


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


def _detector_input() -> DetectorInput:
    return DetectorInput(
        title="Как выбрать матрас",
        content_markdown="# Текст",
        language="ru",
    )


def _humanizer_input() -> HumanizerInput:
    return HumanizerInput(
        title="Как выбрать матрас",
        meta_description="Гид",
        url_slug="kak-vybrat-matras",
        content_markdown="# Текст\n\n![Кадр](images/image-1.png)\n",
        language="ru",
        audience="general",
        detector_notes="ровный ритм",
    )


def _summary_input() -> SummaryInput:
    return SummaryInput(
        title="Как выбрать матрас",
        content_markdown="# Длинная статья",
        language="ru",
        target_char_count=500,
    )


@pytest.mark.asyncio
async def test_detector_parses_json() -> None:
    payload = {
        "ai_likelihood": 40,
        "uniqueness": 70,
        "notes": "Стиль ровный",
        "signals": [{"name": "even_rhythm", "detail": "Одинаковые абзацы"}],
    }
    detector = OpenAIDetector(
        api_key="sk-test",
        client=FakeClient(json.dumps(payload)),
    )
    output = await detector.scan(_detector_input())
    assert output.ai_likelihood == 40
    assert output.uniqueness == 70
    assert output.signals[0].name == "even_rhythm"


@pytest.mark.asyncio
async def test_detector_rejects_invalid_json() -> None:
    detector = OpenAIDetector(api_key="sk-test", client=FakeClient("not-json"))
    with pytest.raises(AIValidationError):
        await detector.scan(_detector_input())


@pytest.mark.asyncio
async def test_humanizer_parses_json() -> None:
    payload = {
        "title": "Как выбрать матрас",
        "meta_description": "Гид",
        "url_slug": "kak-vybrat-matras",
        "content_markdown": "Живой текст.\n\n![Кадр](images/image-1.png)\n",
        "word_count": 4,
    }
    humanizer = OpenAIHumanizer(
        api_key="sk-test",
        client=FakeClient(json.dumps(payload)),
    )
    output = await humanizer.humanize(_humanizer_input())
    assert "Живой текст" in output.content_markdown
    assert "images/image-1.png" in output.content_markdown


@pytest.mark.asyncio
async def test_summarizer_parses_json() -> None:
    payload = {"summary": "Коротко о выборе матраса по жесткости."}
    summarizer = OpenAISummarizer(
        api_key="sk-test",
        client=FakeClient(json.dumps(payload)),
    )
    output = await summarizer.summarize(_summary_input())
    assert "жесткости" in output.summary
