"""OpenAI-backed SeoAgent."""

from __future__ import annotations

from pathlib import Path

from openai import AsyncOpenAI

from app.config import Settings, get_settings
from app.schemas.pipeline import SeoPlanInput, SeoPlanOutput
from app.services.ai.openai_json import OpenAIJsonCaller
from app.services.ai.prompt_loader import load_system_prompt, render_seo_brief_prompt


class OpenAISeoAgent:
    """Refines outline and SEO hints via chat completions. No API call on init."""

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
            failure_label="SEO planning",
            api_key=api_key,
            model=model,
            base_url=base_url,
            client=client,
            settings=resolved,
            max_tokens=2000,
        )

    async def plan(self, request: SeoPlanInput) -> SeoPlanOutput:
        system_prompt = load_system_prompt(prompts_dir=self._prompts_dir)
        prompt = render_seo_brief_prompt(request, prompts_dir=self._prompts_dir)
        return await self._caller.complete_json(system_prompt, prompt, SeoPlanOutput)
