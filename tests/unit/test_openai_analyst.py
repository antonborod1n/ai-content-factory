"""OpenAICompetitorAnalyst with a fake AsyncOpenAI client."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.exceptions import AIValidationError
from app.schemas.research import CompetitorPlanInput, CompetitorProfile
from app.services.ai.openai_analyst import OpenAICompetitorAnalyst


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    async def create(self, **_kwargs: Any) -> SimpleNamespace:
        message = SimpleNamespace(content=self._content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def _input() -> CompetitorPlanInput:
    return CompetitorPlanInput(
        topic="Матрас",
        word_count=3000,
        competitors=[
            CompetitorProfile(
                rank=1,
                title="A",
                url="https://example.com/a",
                headings=["Вес", "Поза"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_analyst_parses_json_outline() -> None:
    payload = {
        "outline": ["Вес покупателя", "Поза сна", "FAQ", "Заключение"],
        "title_hint": "Как выбрать жесткость матраса",
        "meta_description_hint": "Гид",
        "url_slug_hint": "kak-vybrat-zhestkost",
        "article_goal": "Лучше выдачи",
        "notes": "Нет таблицы по весу",
    }
    analyst = OpenAICompetitorAnalyst(
        api_key="sk-test",
        client=FakeClient(__import__("json").dumps(payload)),
    )
    plan = await analyst.plan(_input())
    assert plan.outline[0] == "Вес покупателя"
    assert plan.url_slug_hint == "kak-vybrat-zhestkost"


@pytest.mark.asyncio
async def test_analyst_rejects_invalid_json() -> None:
    analyst = OpenAICompetitorAnalyst(api_key="sk-test", client=FakeClient("not-json"))
    with pytest.raises(AIValidationError):
        await analyst.plan(_input())
