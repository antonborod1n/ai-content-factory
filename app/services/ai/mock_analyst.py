"""Deterministic CompetitorAnalyst for tests."""

from __future__ import annotations

from app.core.exceptions import AIError
from app.schemas.ai import CompetitorPlanOutput
from app.schemas.research import CompetitorPlanInput


class MockCompetitorAnalyst:
    """Builds an outline from competitor headings; never calls a provider."""

    def __init__(
        self,
        *,
        output: CompetitorPlanOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[CompetitorPlanInput] = []

    async def plan(self, request: CompetitorPlanInput) -> CompetitorPlanOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock competitor analyst failed") from self.fail_with
        if self.output is not None:
            return self.output

        headings: list[str] = []
        seen: set[str] = set()
        for profile in request.competitors:
            for heading in profile.headings:
                key = heading.casefold()
                if key in seen:
                    continue
                seen.add(key)
                headings.append(heading)
        if len(headings) < 2:
            headings = [
                "Почему жесткость матраса важна",
                "Как учесть вес и позу сна",
                "FAQ",
                "Заключение",
            ]
        if "faq" not in seen:
            headings.append("FAQ")
        if "заключение" not in seen:
            headings.append("Заключение")
        return CompetitorPlanOutput(
            outline=headings[:10],
            title_hint=f"Как выбрать: {request.topic}",
            meta_description_hint=(
                "Разбор жесткости матраса по весу и позе сна, "
                "без копирования конкурентов."
            ),
            url_slug_hint="kak-vybrat-zhestkost-matrasa",
            article_goal="Дать план выбора жесткости лучше, чем у ТОП выдачи",
            notes="Mock outline from competitor headings",
        )
