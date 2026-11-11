"""OpenAI-backed TopicPlanner."""

from __future__ import annotations

from pathlib import Path

from openai import AsyncOpenAI

from app.config import Settings, get_settings
from app.schemas.discovery import TopicPlanInput, TopicPlanOutput
from app.services.ai.openai_json import OpenAIJsonCaller
from app.services.ai.prompt_loader import (
    load_system_prompt,
    render_topic_discovery_prompt,
)


class OpenAITopicPlanner:
    """Clusters SERP candidates via chat completions. No API call on init."""

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
            failure_label="Topic discovery",
            api_key=api_key,
            model=model,
            base_url=base_url,
            client=client,
            settings=resolved,
            max_tokens=4000,
        )

    async def plan(self, request: TopicPlanInput) -> TopicPlanOutput:
        system_prompt = load_system_prompt(prompts_dir=self._prompts_dir)
        prompt = render_topic_discovery_prompt(
            request, prompts_dir=self._prompts_dir
        )
        return await self._caller.complete_json(system_prompt, prompt, TopicPlanOutput)
