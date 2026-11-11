"""Deterministic Summarizer for tests."""

from __future__ import annotations

from app.core.exceptions import AIError
from app.schemas.quality import SummaryInput, SummaryOutput


class MockSummarizer:
    """Returns a short summary from the title; never calls a provider."""

    def __init__(
        self,
        *,
        output: SummaryOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[SummaryInput] = []

    async def summarize(self, request: SummaryInput) -> SummaryOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock summarizer failed") from self.fail_with
        if self.output is not None:
            return self.output
        return SummaryOutput(summary=f"Кратко: {request.title}.")
