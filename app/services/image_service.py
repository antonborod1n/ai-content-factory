"""Replace IMAGE_/INFOGRAPHIC_PLACEHOLDER tokens with generated files."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.core.exceptions import AIConfigurationError, AIError
from app.core.placeholders import (
    ContentPlaceholder,
    asset_relative_path,
    ensure_cover_placeholder,
    find_placeholders,
    replace_placeholder,
)
from app.schemas.enrichment import GeneratedAsset
from app.services.ai.image_provider import ImageProvider
from app.services.ai.prompt_loader import render_image_generate_prompt

logger = logging.getLogger(__name__)


class ImageService:
    """Orchestrates placeholder → provider → markdown path. No SQL, no SDK."""

    def __init__(
        self,
        provider: ImageProvider,
        *,
        enabled: bool | None = None,
    ) -> None:
        settings = get_settings()
        self._provider = provider
        self._enabled = settings.images_enabled if enabled is None else enabled

    async def replace_placeholders(
        self,
        markdown: str,
        *,
        topic: str,
        title: str = "",
        kinds: set[str] | None = None,
        ensure_hero: bool = False,
    ) -> tuple[str, list[GeneratedAsset]]:
        """Generate images for placeholders. Failures skip that token only."""
        updated = markdown
        if ensure_hero:
            updated = ensure_cover_placeholder(updated, title=title or topic)
        tokens = find_placeholders(updated)
        if kinds is not None:
            tokens = [item for item in tokens if item.kind in kinds]
        if not tokens:
            return updated, []
        if not self._enabled:
            logger.info(
                "Image enrichment disabled; leaving %s placeholders",
                len(tokens),
            )
            return updated, [_skipped(item) for item in tokens]

        assets: list[GeneratedAsset] = []
        for index, item in enumerate(tokens):
            path = asset_relative_path(item.kind, item.number)
            heading, excerpt, alt = _scene_for_slot(
                item, topic=topic, title=title
            )
            prompt = render_image_generate_prompt(
                topic=topic,
                alt=alt,
                kind=item.kind,
                heading=heading,
                excerpt=excerpt,
                title=title,
            )
            try:
                data = await self._provider.generate(prompt, kind=item.kind)
            except AIConfigurationError:
                logger.info("Image provider is not configured; skipping remaining")
                assets.extend(_skipped(rest) for rest in tokens[index:])
                return updated, assets
            except AIError:
                logger.warning(
                    "Image generation failed for %s; keeping placeholder",
                    item.token,
                )
                assets.append(_failed(item, path))
                continue
            if not data:
                assets.append(_failed(item, path))
                continue
            updated = replace_placeholder(updated, item.token, path)
            assets.append(
                GeneratedAsset(
                    kind=item.kind,
                    placeholder=item.token,
                    alt=item.alt,
                    path=path,
                    status="completed",
                    data=data,
                )
            )
        logger.info(
            "Images finished completed=%s failed=%s skipped=%s",
            sum(1 for item in assets if item.status == "completed"),
            sum(1 for item in assets if item.status == "failed"),
            sum(1 for item in assets if item.status == "skipped"),
        )
        return updated, assets


def _skipped(item: ContentPlaceholder) -> GeneratedAsset:
    return GeneratedAsset(
        kind=item.kind,
        placeholder=item.token,
        alt=item.alt,
        path=asset_relative_path(item.kind, item.number),
        status="skipped",
    )


def _failed(item: ContentPlaceholder, path: str) -> GeneratedAsset:
    return GeneratedAsset(
        kind=item.kind,
        placeholder=item.token,
        alt=item.alt,
        path=path,
        status="failed",
    )


def _scene_for_slot(
    item: ContentPlaceholder, *, topic: str, title: str
) -> tuple[str, str, str]:
    """Hero slots illustrate the article title, not a nearby section."""
    if item.kind == "hero":
        name = (title or item.alt or topic).strip()
        return name, "", name
    return item.heading, item.excerpt, item.alt
