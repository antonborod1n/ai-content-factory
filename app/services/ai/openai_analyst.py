"""OpenAI-backed CompetitorAnalyst."""

from __future__ import annotations

import logging
from pathlib import Path

from openai import APIError, AsyncOpenAI, OpenAIError

from app.config import Settings, get_settings
from app.core.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIValidationError,
)
from app.schemas.ai import CompetitorPlanOutput
from app.schemas.research import CompetitorPlanInput
from app.services.ai.openai_client import build_async_openai
from app.services.ai.openai_json import parse_model_json
from app.services.ai.prompt_loader import (
    load_system_prompt,
    render_competitor_outline_prompt,
)

logger = logging.getLogger(__name__)


class OpenAICompetitorAnalyst:
    """Plans an improved outline via chat completions. No API call on init."""

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
        self._api_key = resolved.openai_api_key if api_key is None else api_key
        self._model = resolved.openai_model if model is None else model
        self._base_url = resolved.openai_base_url if base_url is None else base_url
        self._timeout = resolved.openai_timeout_seconds
        self._temperature = resolved.openai_temperature
        self._prompts_dir = prompts_dir
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def _get_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        if not self.is_configured:
            raise AIConfigurationError("OpenAI API key is not configured")
        self._client = build_async_openai(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        return self._client

    async def plan(self, request: CompetitorPlanInput) -> CompetitorPlanOutput:
        system_prompt = load_system_prompt(prompts_dir=self._prompts_dir)
        prompt = render_competitor_outline_prompt(
            request, prompts_dir=self._prompts_dir
        )
        try:
            return parse_model_json(
                await self._complete(system_prompt, prompt), CompetitorPlanOutput
            )
        except AIValidationError:
            logger.warning("Competitor outline reply was invalid; retrying once")
        return parse_model_json(
            await self._complete(system_prompt, prompt), CompetitorPlanOutput
        )

    async def _complete(self, system_prompt: str, prompt: str) -> str:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature,
                max_tokens=2000,
            )
        except AIConfigurationError:
            raise
        except (APIError, OpenAIError) as exc:
            logger.exception("OpenAI provider error during competitor outline")
            raise AIProviderError(
                "Competitor outline failed due to an AI provider error"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during competitor outline")
            raise AIProviderError(
                "Competitor outline failed due to an AI provider error"
            ) from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise AIValidationError("AI response failed validation") from exc
        if not content or not str(content).strip():
            raise AIValidationError("AI response failed validation")
        return str(content)
