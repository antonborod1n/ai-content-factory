"""Summarizer protocol — short excerpt of a completed article."""

from __future__ import annotations

from typing import Protocol

from app.schemas.quality import SummaryInput, SummaryOutput


class Summarizer(Protocol):
    """Writes a short summary. AI layer only — no persistence."""

    async def summarize(self, request: SummaryInput) -> SummaryOutput:
        """Return a short plain-text summary."""
        ...
