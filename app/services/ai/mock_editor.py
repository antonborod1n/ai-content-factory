"""Deterministic Editor for tests."""

from __future__ import annotations

from app.core.exceptions import AIError
from app.schemas.ai import AIArticleOutput
from app.schemas.pipeline import EditorInput


class MockEditor:
    """Returns an edited copy of the draft; never calls a provider."""

    def __init__(
        self,
        *,
        output: AIArticleOutput | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail_with = fail_with
        self.calls: list[EditorInput] = []

    async def edit(self, request: EditorInput) -> AIArticleOutput:
        self.calls.append(request)
        if self.fail_with is not None:
            if isinstance(self.fail_with, AIError):
                raise self.fail_with
            raise AIError("Mock editor failed") from self.fail_with
        if self.output is not None:
            return self.output

        draft = request.draft
        title = draft.title
        if not title.startswith("Edited: "):
            title = f"Edited: {title}"
        markdown = draft.content_markdown.rstrip() + "\n\nПояснение от редактора.\n"
        return AIArticleOutput(
            title=title,
            meta_description=draft.meta_description,
            content_markdown=markdown,
            word_count=len(markdown.split()),
            url_slug=draft.url_slug,
        )
