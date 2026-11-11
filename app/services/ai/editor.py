"""Editor protocol — polish a draft after fact-check."""

from __future__ import annotations

from typing import Protocol

from app.schemas.ai import AIArticleOutput
from app.schemas.pipeline import EditorInput


class Editor(Protocol):
    """Applies fact-check notes and copy-edits. AI layer only."""

    async def edit(self, request: EditorInput) -> AIArticleOutput:
        """Return the full edited article JSON. Do not invent new facts."""
        ...
