"""OpenAI-backed AIWriter implementation."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, TypeVar

from openai import APIError, AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.core.exceptions import (
    AIConfigurationError,
    AIError,
    AIProviderError,
    AIValidationError,
)
from app.core.word_count import count_words
from app.schemas.ai import (
    AIArticleMetaOutput,
    AIArticleOutput,
    AISectionOutput,
    ArticleWriteInput,
)
from app.services.ai.prompt_loader import (
    load_system_prompt,
    render_article_expand_prompt,
    render_article_meta_prompt,
    render_article_section_prompt,
    render_article_writer_prompt,
    target_word_count,
)
from app.services.ai.section_plan import SectionPlan, build_section_plans

logger = logging.getLogger(__name__)

_PayloadT = TypeVar("_PayloadT", bound=BaseModel)

_JSON_FENCE_RE = re.compile(
    r"^```(?:json)?\s*(?P<body>.*?)\s*```$",
    re.DOTALL | re.IGNORECASE,
)


class OpenAIWriter:
    """Generates articles via the OpenAI API. Does not call the API on init."""

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
        self._temperature = resolved.openai_temperature
        self._max_tokens = resolved.openai_max_tokens
        self._target_word_count = resolved.article_target_word_count
        self._min_word_ratio = resolved.article_min_word_ratio
        self._expand_attempts = resolved.article_expand_attempts
        self._prompts_dir = prompts_dir
        self._client = client

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str | None:
        """Custom API endpoint, e.g. an OpenAI-compatible gateway."""
        return self._base_url

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def _get_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        if not self.is_configured:
            raise AIConfigurationError("OpenAI API key is not configured")
        if self._base_url:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        else:
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def generate(self, request: ArticleWriteInput) -> AIArticleOutput:
        system_prompt = load_system_prompt(prompts_dir=self._prompts_dir)
        target = target_word_count(request, self._target_word_count)
        plans = build_section_plans(request, target_word_count=target)
        if plans:
            return await self._generate_by_sections(request, system_prompt, plans)

        prompt = render_article_writer_prompt(
            request,
            default_word_count=self._target_word_count,
            prompts_dir=self._prompts_dir,
        )
        raw_content = await self._complete(system_prompt, prompt)
        article = self._parse_and_validate(raw_content)
        return await self._expand_to_target(request, system_prompt, article)

    async def _generate_by_sections(
        self,
        request: ArticleWriteInput,
        system_prompt: str,
        plans: list[SectionPlan],
    ) -> AIArticleOutput:
        """Write the SEO wrapper, then one request per outline section."""
        meta = self._parse(
            await self._complete(
                system_prompt,
                render_article_meta_prompt(
                    request,
                    default_word_count=self._target_word_count,
                    prompts_dir=self._prompts_dir,
                ),
            ),
            AIArticleMetaOutput,
        )

        parts = [f"# **{meta.title}**"]
        written: list[str] = []
        for plan in plans:
            section = self._parse(
                await self._complete(
                    system_prompt,
                    render_article_section_prompt(
                        request,
                        plan=plan,
                        title=meta.title,
                        previous_sections=written,
                        default_word_count=self._target_word_count,
                        prompts_dir=self._prompts_dir,
                    ),
                ),
                AISectionOutput,
            )
            parts.append(section.content_markdown.strip())
            written.append(plan.title)

        content_markdown = "\n\n".join(parts)
        return AIArticleOutput(
            title=meta.title,
            meta_description=meta.meta_description,
            url_slug=meta.url_slug,
            content_markdown=content_markdown,
            word_count=count_words(content_markdown),
        )

    async def _expand_to_target(
        self,
        request: ArticleWriteInput,
        system_prompt: str,
        article: AIArticleOutput,
    ) -> AIArticleOutput:
        """Grow a draft that came back well below the requested length.

        Keeps the longest valid version: a failed or non-growing expansion
        leaves the previous article untouched.
        """
        target = target_word_count(request, self._target_word_count)
        minimum = int(target * self._min_word_ratio)
        words = count_words(article.content_markdown)

        for _ in range(self._expand_attempts):
            if words >= minimum:
                break
            prompt = render_article_expand_prompt(
                request,
                current=article,
                current_word_count=words,
                default_word_count=self._target_word_count,
                prompts_dir=self._prompts_dir,
            )
            try:
                candidate = self._parse_and_validate(
                    await self._complete(system_prompt, prompt)
                )
            except AIError:
                logger.warning(
                    "Expansion pass failed; keeping the %s-word draft", words
                )
                break

            candidate_words = count_words(candidate.content_markdown)
            if candidate_words <= words:
                break
            article, words = candidate, candidate_words

        if words < minimum:
            logger.info(
                "Article is %s words, below the %s-word target", words, target
            )
        return article

    async def _complete(self, system_prompt: str, prompt: str) -> str:
        client = self._get_client()
        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
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
            logger.exception("OpenAI provider error during article generation")
            raise AIProviderError(
                "Article generation failed due to an AI provider error"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during OpenAI article generation")
            raise AIProviderError(
                "Article generation failed due to an AI provider error"
            ) from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise AIValidationError(
                "AI response failed validation"
            ) from exc

        if not content or not str(content).strip():
            raise AIValidationError("AI response failed validation")
        return str(content)

    def _parse_and_validate(self, raw_content: str) -> AIArticleOutput:
        return self._parse(raw_content, AIArticleOutput)

    def _parse(
        self, raw_content: str, model: type[_PayloadT]
    ) -> _PayloadT:
        payload = self._extract_json_object(raw_content)
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            raise AIValidationError(
                "AI response failed validation"
            ) from exc

    @staticmethod
    def _extract_json_object(raw_content: str) -> dict[str, Any]:
        text = raw_content.strip()
        fence_match = _JSON_FENCE_RE.match(text)
        if fence_match is not None:
            text = fence_match.group("body").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIValidationError(
                "AI response failed validation"
            ) from exc
        if not isinstance(data, dict):
            raise AIValidationError("AI response failed validation")
        return data
