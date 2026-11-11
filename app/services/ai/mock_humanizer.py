"""Deterministic Humanizer for tests."""

from __future__ import annotations

from app.core.exceptions import AIError
from app.core.word_count import count_words
from app.schemas.ai import AIArticleOutput
from app.schemas.quality import HumanizerInput


class MockHumanizer:
    """Marks the draft as humanized; never calls a provider."""

    def __init__(
        self,
        *,
        output: AIArticleOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[HumanizerInput] = []

    async def humanize(self, request: HumanizerInput) -> AIArticleOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock humanizer failed") from self.fail_with
        if self.output is not None:
            return self.output
        markdown = (
            request.content_markdown.rstrip() + "\n\nТекст звучит естественнее.\n"
        )
        return AIArticleOutput(
            title=request.title,
            meta_description=request.meta_description,
            content_markdown=markdown,
            word_count=count_words(markdown),
            url_slug=request.url_slug,
        )
