"""Deterministic SeoAgent for tests."""

from __future__ import annotations

from app.core.exceptions import AIError
from app.schemas.pipeline import SeoPlanInput, SeoPlanOutput


class MockSeoAgent:
    """Builds a plan from the brief; never calls a provider."""

    def __init__(
        self,
        *,
        output: SeoPlanOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[SeoPlanInput] = []

    async def plan(self, request: SeoPlanInput) -> SeoPlanOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock SEO agent failed") from self.fail_with
        if self.output is not None:
            return self.output

        outline = list(request.outline)
        if len(outline) < 2:
            outline = [
                "Зачем это важно",
                "Как выбрать",
                "FAQ",
                "Заключение",
            ]
        primary = list(request.primary_keywords or request.keywords) or [
            request.topic
        ]
        return SeoPlanOutput(
            outline=outline,
            primary_keywords=primary,
            secondary_keywords=list(request.secondary_keywords),
            search_intent=request.search_intent or "informational_commercial",
            title_hint=f"SEO: {request.topic}",
            meta_description_hint=f"Краткий гид: {request.topic}",
            url_slug_hint="mock-seo-slug",
            article_goal=request.article_goal or "Дать практический ответ лучше выдачи",
            notes="Mock SEO plan",
        )
