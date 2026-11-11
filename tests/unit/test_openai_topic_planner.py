"""OpenAI TopicPlanner with a fake AsyncOpenAI client."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.exceptions import AIValidationError
from app.schemas.discovery import (
    CandidateKind,
    SearchEngine,
    TopicCandidate,
    TopicPlanInput,
)
from app.services.ai.openai_topic_planner import OpenAITopicPlanner


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


def _input() -> TopicPlanInput:
    return TopicPlanInput(
        niche="матрасы",
        seeds=["жесткость матраса"],
        max_topics=3,
        candidates=[
            TopicCandidate(
                text="Как выбрать жесткость матраса",
                kind=CandidateKind.ORGANIC,
                engine=SearchEngine.GOOGLE,
                query="жесткость матраса",
            )
        ],
    )


@pytest.mark.asyncio
async def test_topic_planner_parses_json() -> None:
    payload = {
        "topics": [
            {
                "topic": "Как выбрать жесткость матраса",
                "primary_keywords": ["жесткость матраса"],
                "secondary_keywords": ["кокос"],
                "article_goal": "Помочь выбрать",
                "outline": ["Вес", "Поза", "FAQ"],
                "search_intent": "informational_commercial",
            }
        ]
    }
    planner = OpenAITopicPlanner(
        api_key="sk-test",
        client=FakeClient(__import__("json").dumps(payload)),
    )
    plan = await planner.plan(_input())
    assert plan.topics[0].topic == "Как выбрать жесткость матраса"
    assert plan.topics[0].outline[0] == "Вес"


@pytest.mark.asyncio
async def test_topic_planner_rejects_invalid_json() -> None:
    planner = OpenAITopicPlanner(api_key="sk-test", client=FakeClient("not-json"))
    with pytest.raises(AIValidationError):
        await planner.plan(_input())
