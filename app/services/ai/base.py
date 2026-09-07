"""AIWriter protocol and shared AI contracts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.ai import AIArticleOutput, ArticleWriteInput

__all__ = ["AIArticleOutput", "AIWriter", "ArticleWriteInput"]


@runtime_checkable
class AIWriter(Protocol):
    """Abstraction for article generation providers."""

    async def generate(self, request: ArticleWriteInput) -> AIArticleOutput:
        """Generate a structured article for the given request."""
        ...
