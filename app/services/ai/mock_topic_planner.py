"""Deterministic TopicPlanner for tests."""

from __future__ import annotations

from app.core.exceptions import AIError
from app.core.topic_candidates import dedupe_texts, normalize_topic_text
from app.schemas.discovery import (
    CandidateKind,
    TopicBriefDraft,
    TopicPlanInput,
    TopicPlanOutput,
)


class MockTopicPlanner:
    """Builds briefs from candidate texts; never calls a provider."""

    def __init__(
        self,
        *,
        output: TopicPlanOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[TopicPlanInput] = []

    async def plan(self, request: TopicPlanInput) -> TopicPlanOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock topic planner failed") from self.fail_with
        if self.output is not None:
            return self.output

        texts = [item.text for item in request.candidates]
        if not texts:
            texts = list(request.seeds)
        unique = dedupe_texts(texts)[: request.max_topics]
        topics: list[TopicBriefDraft] = []
        for text in unique:
            keywords = [text]
            seed = request.seeds[0] if request.seeds else text
            if normalize_topic_text(seed) != normalize_topic_text(text):
                keywords.append(seed)
            kind = next(
                (
                    item.kind
                    for item in request.candidates
                    if normalize_topic_text(item.text) == normalize_topic_text(text)
                ),
                CandidateKind.ORGANIC,
            )
            goal = (
                f"Ответить на вопрос: {text}"
                if kind == CandidateKind.PAA or text.endswith("?")
                else f"Дать практическое руководство: {text}"
            )
            topics.append(
                TopicBriefDraft(
                    topic=text,
                    primary_keywords=keywords[:2],
                    secondary_keywords=[],
                    article_goal=goal,
                    outline=[
                        "Что важно знать",
                        "Как выбрать",
                        "Типичные ошибки",
                        "FAQ",
                        "Заключение",
                    ],
                    search_intent="informational_commercial",
                )
            )
        return TopicPlanOutput(topics=topics)
