"""Deterministic ContentGapAnalyst for tests."""

from __future__ import annotations

from app.core.competitor_plan import CompetitorPlanTopic
from app.core.exceptions import AIError
from app.core.topic_candidates import dedupe_texts
from app.schemas.competitor_topics import ContentGapInput, ContentGapOutput


class MockContentGapAnalyst:
    """Builds plan rows from unique hit texts; never calls a provider."""

    def __init__(
        self,
        *,
        output: ContentGapOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[ContentGapInput] = []

    async def analyze(self, request: ContentGapInput) -> ContentGapOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock content-gap analyst failed") from self.fail_with
        if self.output is not None:
            return self.output
        unique = dedupe_texts(item.text for item in request.hits)[: request.max_topics]
        topics: list[CompetitorPlanTopic] = []
        for text in unique:
            owners = [
                item.competitor
                for item in request.hits
                if item.text == text and item.competitor
            ]
            competitors = list(dict.fromkeys(owners))
            topics.append(
                CompetitorPlanTopic(
                    title=text,
                    category="",
                    priority="High" if len(competitors) > 1 else "Medium",
                    competitors=competitors,
                    is_gap=not competitors,
                    unique_angle=f"Тема по сигналу конкурентов: {text}",
                    intent="informational / howto",
                    commercial_link=request.domain or "",
                )
            )
        return ContentGapOutput(topics=topics)
