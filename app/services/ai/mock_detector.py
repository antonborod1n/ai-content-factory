"""Deterministic AiDetector for tests."""

from __future__ import annotations

from app.core.exceptions import AIError
from app.schemas.quality import DetectorInput, DetectorOutput, DetectorSignal


class MockAiDetector:
    """Returns fixed scores; never calls a provider."""

    def __init__(
        self,
        *,
        output: DetectorOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[DetectorInput] = []

    async def scan(self, request: DetectorInput) -> DetectorOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock detector failed") from self.fail_with
        if self.output is not None:
            return self.output
        return DetectorOutput(
            ai_likelihood=32,
            uniqueness=78,
            notes="Mock detector: стиль в порядке",
            signals=[
                DetectorSignal(name="even_rhythm", detail="Ровный ритм абзацев")
            ],
        )
