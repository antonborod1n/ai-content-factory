"""OpenAI Stage 4 agents with a fake AsyncOpenAI client."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.exceptions import AIValidationError
from app.schemas.ai import AIArticleOutput
from app.schemas.pipeline import (
    EditorInput,
    FactCheckInput,
    FactCheckOutput,
    SeoPlanInput,
)
from app.services.ai.openai_editor import OpenAIEditor
from app.services.ai.openai_fact_checker import OpenAIFactChecker
from app.services.ai.openai_seo_agent import OpenAISeoAgent


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.kwargs = kwargs
        message = SimpleNamespace(content=self._content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class FakeClient:
    def __init__(self, content: str) -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def _seo_input() -> SeoPlanInput:
    return SeoPlanInput(
        topic="Матрас",
        word_count=3000,
        outline=["Вес", "Поза"],
        competitor_context="H2: вес, поза",
    )


@pytest.mark.asyncio
async def test_seo_agent_parses_json_plan() -> None:
    payload = {
        "outline": ["Вес покупателя", "Поза сна", "FAQ", "Заключение"],
        "primary_keywords": ["жесткость матраса"],
        "secondary_keywords": ["кокос"],
        "search_intent": "informational_commercial",
        "title_hint": "Как выбрать жесткость матраса",
        "meta_description_hint": "Гид",
        "url_slug_hint": "kak-vybrat-zhestkost",
        "article_goal": "Лучше выдачи",
        "notes": "Нет таблицы по весу",
    }
    agent = OpenAISeoAgent(
        api_key="sk-test",
        client=FakeClient(__import__("json").dumps(payload)),
    )
    plan = await agent.plan(_seo_input())
    assert plan.outline[0] == "Вес покупателя"
    assert plan.url_slug_hint == "kak-vybrat-zhestkost"


@pytest.mark.asyncio
async def test_seo_agent_rejects_invalid_json() -> None:
    agent = OpenAISeoAgent(api_key="sk-test", client=FakeClient("not-json"))
    with pytest.raises(AIValidationError):
        await agent.plan(_seo_input())


@pytest.mark.asyncio
async def test_fact_checker_parses_verdict() -> None:
    payload = {
        "verdict": "needs_revision",
        "issues": [
            {
                "severity": "warning",
                "claim": "Гарантия 100 лет",
                "problem": "Нет источника",
                "suggestion": "Смягчить",
            }
        ],
        "notes": "Проверить цифры",
    }
    checker = OpenAIFactChecker(
        api_key="sk-test",
        client=FakeClient(__import__("json").dumps(payload)),
    )
    report = await checker.review(
        FactCheckInput(
            topic="Матрас",
            title="T",
            meta_description="M",
            content_markdown="# Тело",
        )
    )
    assert report.verdict == "needs_revision"
    assert report.issues[0].claim == "Гарантия 100 лет"


@pytest.mark.asyncio
async def test_editor_parses_article_json() -> None:
    payload = {
        "title": "Вычитанный заголовок",
        "meta_description": "Meta",
        "url_slug": "vychitannyy",
        "content_markdown": "# Тело\n\nТекст.",
        "word_count": 3,
    }
    editor = OpenAIEditor(
        api_key="sk-test",
        client=FakeClient(__import__("json").dumps(payload)),
    )
    result = await editor.edit(
        EditorInput(
            topic="Матрас",
            draft=AIArticleOutput(
                title="Черновик",
                meta_description="Meta",
                content_markdown="# Черновик",
                word_count=2,
            ),
            fact_check=FactCheckOutput(verdict="ok"),
        )
    )
    assert result.title == "Вычитанный заголовок"
    assert result.url_slug == "vychitannyy"
