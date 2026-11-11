"""Deterministic FactChecker for tests."""

from __future__ import annotations

from app.core.exceptions import AIError
from app.schemas.pipeline import FactCheckInput, FactCheckIssue, FactCheckOutput


class MockFactChecker:
    """Returns a configured verdict; never calls a provider."""

    def __init__(
        self,
        *,
        output: FactCheckOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[FactCheckInput] = []

    async def review(self, request: FactCheckInput) -> FactCheckOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock fact checker failed") from self.fail_with
        if self.output is not None:
            return self.output
        return FactCheckOutput(
            verdict="ok",
            issues=[],
            notes="Mock fact-check passed",
        )


def needs_revision_output() -> FactCheckOutput:
    """Helper for tests that want a non-ok verdict."""
    return FactCheckOutput(
        verdict="needs_revision",
        issues=[
            FactCheckIssue(
                severity="warning",
                claim="Неподтверждённая цифра",
                problem="Нет источника в базе знаний",
                suggestion="Убрать точное число или смягчить формулировку",
            )
        ],
        notes="Mock fact-check found issues",
    )
