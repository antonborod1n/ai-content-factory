"""AiDetector protocol — style/uniqueness scores, not a web plagiarism API."""

from __future__ import annotations

from typing import Protocol

from app.schemas.quality import DetectorInput, DetectorOutput


class AiDetector(Protocol):
    """Estimates AI-likeness and uniqueness. AI layer only — no persistence."""

    async def scan(self, request: DetectorInput) -> DetectorOutput:
        """Return numeric scores. Do not log the article body."""
        ...
