"""Deterministic DzenWriter for tests."""

from __future__ import annotations

from app.core.exceptions import AIError
from app.core.word_count import count_characters
from app.schemas.dzen import DzenArticleOutput, DzenWriteInput


class MockDzenWriter:
    """Returns a short article with cover + two in-body image slots."""

    def __init__(
        self,
        *,
        output: DzenArticleOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[DzenWriteInput] = []

    async def generate(self, request: DzenWriteInput) -> DzenArticleOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock Dzen writer failed") from self.fail_with
        if self.output is not None:
            return self.output

        title = request.source_title
        content_markdown = (
            f"![Главная](DZEN_COVER_PLACEHOLDER)\n\n"
            f"# **{title}**\n\n"
            f"Короткая версия: {title}.\n\n"
            f"![Кадр в тексте](DZEN_IMAGE_PLACEHOLDER_1)\n\n"
            f"Тот же материал, меньше по объёму.\n\n"
            f"![Второй кадр](DZEN_IMAGE_PLACEHOLDER_2)\n\n"
            f"Краткий вывод.\n"
        )
        return DzenArticleOutput(
            title=title,
            content_markdown=content_markdown,
            char_count=count_characters(content_markdown),
        )
