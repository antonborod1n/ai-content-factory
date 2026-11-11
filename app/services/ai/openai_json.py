"""Shared JSON chat-completion helpers for Stage 4 OpenAI agents."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from openai import APIError, AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.core.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIValidationError,
)
from app.services.ai.openai_client import build_async_openai

logger = logging.getLogger(__name__)

_PayloadT = TypeVar("_PayloadT", bound=BaseModel)

_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*(?P<body>\{.*\})\s*```",
    re.DOTALL | re.IGNORECASE,
)


class OpenAIJsonCaller:
    """Thin chat JSON caller. Does not call the provider on init."""

    def __init__(
        self,
        *,
        failure_label: str,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        client: AsyncOpenAI | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self._failure_label = failure_label
        self._api_key = resolved.openai_api_key if api_key is None else api_key
        self._model = resolved.openai_model if model is None else model
        self._base_url = resolved.openai_base_url if base_url is None else base_url
        self._temperature = (
            resolved.openai_temperature if temperature is None else temperature
        )
        self._max_tokens = max_tokens
        self._timeout = resolved.openai_timeout_seconds
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

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self._temperature,
        }
        if self._max_tokens is not None:
            request_kwargs["max_tokens"] = self._max_tokens

        try:
            response = await client.chat.completions.create(**request_kwargs)
        except AIConfigurationError:
            raise
        except (APIError, OpenAIError) as exc:
            logger.exception("OpenAI provider error during %s", self._failure_label)
            raise AIProviderError(
                f"{self._failure_label} failed due to an AI provider error"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during %s", self._failure_label)
            raise AIProviderError(
                f"{self._failure_label} failed due to an AI provider error"
            ) from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise AIValidationError("AI response failed validation") from exc
        if not content or not str(content).strip():
            raise AIValidationError("AI response failed validation")
        return str(content)

    def parse(self, raw_content: str, model: type[_PayloadT]) -> _PayloadT:
        return parse_model_json(raw_content, model)

    async def complete_json(
        self, system_prompt: str, user_prompt: str, model: type[_PayloadT]
    ) -> _PayloadT:
        """Complete and validate, asking once more if the reply is not valid JSON."""
        try:
            return parse_model_json(
                await self.complete(system_prompt, user_prompt), model
            )
        except AIValidationError:
            logger.warning(
                "%s returned an invalid reply; retrying once", self._failure_label
            )
        return parse_model_json(await self.complete(system_prompt, user_prompt), model)


def parse_model_json[PayloadT: BaseModel](
    raw_content: str, model: type[PayloadT]
) -> PayloadT:
    """Extract the JSON object from a model reply and validate it."""
    payload = extract_json_object(raw_content)
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise AIValidationError("AI response failed validation") from exc


def extract_json_object(raw_content: str) -> dict[str, Any]:
    """Parse the reply as JSON, tolerating a code fence or text around it."""
    text = raw_content.strip()
    # Markdown inside a valid JSON string may itself contain ``` fences,
    # so the whole reply is tried before any fence or brace heuristics.
    candidates = [text]
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match is not None:
        candidates.append(fence_match.group("body").strip())
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise AIValidationError("AI response failed validation")
