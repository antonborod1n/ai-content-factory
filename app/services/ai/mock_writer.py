"""Deterministic AIWriter implementation for tests."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.core.exceptions import AIError, AIValidationError
from app.schemas.ai import AIArticleOutput, ArticleWriteInput


class MockAIWriter:
    """Returns deterministic article output derived from the request topic.

    Tests can force a specific result with ``output``, an error with
    ``fail_with``, or a schema violation with ``invalid_payload``.
    """

    def __init__(
        self,
        *,
        output: AIArticleOutput | None = None,
        fail_with: Exception | None = None,
        invalid_payload: dict[str, Any] | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.invalid_payload = invalid_payload
        self.calls: list[ArticleWriteInput] = []

    async def generate(self, request: ArticleWriteInput) -> AIArticleOutput:
        self.calls.append(request)

        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock AI writer failed") from self.fail_with

        if self.invalid_payload is not None:
            try:
                return AIArticleOutput.model_validate(self.invalid_payload)
            except ValidationError as exc:
                raise AIValidationError(
                    "AI response failed validation"
                ) from exc

        if self.output is not None:
            return self.output

        content_markdown = (
            f"# {request.topic}\n\n"
            f"This is a mock article for {request.audience} "
            f"in language {request.language}."
        )
        if request.keywords:
            content_markdown += (
                "\n\nKeywords: " + ", ".join(request.keywords) + "."
            )

        word_count = len(content_markdown.split())
        return AIArticleOutput(
            title=f"Mock: {request.topic}",
            meta_description=f"Mock meta description for {request.topic}",
            content_markdown=content_markdown,
            word_count=word_count,
        )
