"""OpenAI-backed ContentGapAnalyst."""

from __future__ import annotations

from pathlib import Path

from openai import AsyncOpenAI

from app.config import Settings, get_settings
from app.schemas.competitor_topics import ContentGapInput, ContentGapOutput
from app.services.ai.openai_json import OpenAIJsonCaller
from app.services.ai.prompt_loader import (
    load_system_prompt,
    render_competitor_gap_prompt,
)


class OpenAIContentGapAnalyst:
    """Clusters competitor inventory hits via chat completions."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        prompts_dir: Path | str | None = None,
        client: AsyncOpenAI | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self._prompts_dir = prompts_dir
        self._caller = OpenAIJsonCaller(
            failure_label="Competitor topic analysis",
            api_key=api_key,
            model=model,
            base_url=base_url,
            client=client,
            settings=resolved,
            max_tokens=8000,
        )

    async def analyze(self, request: ContentGapInput) -> ContentGapOutput:
        system_prompt = load_system_prompt(prompts_dir=self._prompts_dir)
        prompt = render_competitor_gap_prompt(
            request, prompts_dir=self._prompts_dir
        )
        return await self._caller.complete_json(system_prompt, prompt, ContentGapOutput)
