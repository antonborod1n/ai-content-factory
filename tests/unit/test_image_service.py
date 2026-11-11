"""Unit tests for ImageService with MockImageProvider."""

import pytest

from app.core.exceptions import AIConfigurationError, AIProviderError
from app.services.ai.mock_image import MINIMAL_PNG, MockImageProvider
from app.services.image_service import ImageService


@pytest.mark.asyncio
async def test_replaces_placeholder_with_relative_path() -> None:
    provider = MockImageProvider()
    service = ImageService(provider, enabled=True)
    markdown = "Текст\n\n![Кадр](IMAGE_PLACEHOLDER_1)\n"

    updated, assets = await service.replace_placeholders(
        markdown, topic="Матрас"
    )

    assert "images/image-1.png" in updated
    assert "IMAGE_PLACEHOLDER_1" not in updated
    assert assets[0].status == "completed"
    assert assets[0].data == MINIMAL_PNG
    assert "data" not in assets[0].model_dump()
    assert provider.calls
    assert "Матрас" in provider.calls[0][0]


@pytest.mark.asyncio
async def test_hero_cover_uses_article_title() -> None:
    provider = MockImageProvider()
    service = ImageService(provider, enabled=True)
    markdown = (
        "# Жесткий или мягкий матрас\n\n"
        "Вступление про выбор.\n\n"
        "![Кадр](IMAGE_PLACEHOLDER_1)\n"
    )

    updated, assets = await service.replace_placeholders(
        markdown,
        topic="Матрас",
        title="Жесткий или мягкий матрас: какой лучше выбрать?",
        ensure_hero=True,
    )

    assert "images/cover.png" in updated
    assert "images/image-1.png" in updated
    assert [item.kind for item in assets] == ["hero", "image"]
    hero_prompt = provider.calls[0][0]
    assert "Жесткий или мягкий матрас: какой лучше выбрать?" in hero_prompt
    assert "hero" in hero_prompt
    assert "Вступление про выбор" not in hero_prompt


@pytest.mark.asyncio
async def test_prompts_differ_by_article_section() -> None:
    provider = MockImageProvider()
    service = ImageService(provider, enabled=True)
    markdown = (
        "## Жёсткий матрас\n\n"
        "Жёсткий блок держит поясницу.\n\n"
        "![Кадр](IMAGE_PLACEHOLDER_1)\n\n"
        "## Мягкий матрас\n\n"
        "Мягкая модель разгружает плечо.\n\n"
        "![Кадр](IMAGE_PLACEHOLDER_2)\n"
    )

    await service.replace_placeholders(markdown, topic="Матрас")

    assert len(provider.calls) == 2
    first, second = provider.calls[0][0], provider.calls[1][0]
    assert first != second
    assert "Жёсткий матрас" in first
    assert "поясницу" in first
    assert "Мягкий матрас" in second
    assert "плечо" in second


@pytest.mark.asyncio
async def test_disabled_leaves_placeholders() -> None:
    provider = MockImageProvider()
    service = ImageService(provider, enabled=False)
    markdown = "![Кадр](IMAGE_PLACEHOLDER_1)"

    updated, assets = await service.replace_placeholders(
        markdown, topic="Матрас"
    )

    assert updated == markdown
    assert assets[0].status == "skipped"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_provider_error_keeps_placeholder() -> None:
    provider = MockImageProvider(fail_with=AIProviderError())
    service = ImageService(provider, enabled=True)
    markdown = "![Кадр](IMAGE_PLACEHOLDER_1)"

    updated, assets = await service.replace_placeholders(
        markdown, topic="Матрас"
    )

    assert "IMAGE_PLACEHOLDER_1" in updated
    assert assets[0].status == "failed"


@pytest.mark.asyncio
async def test_missing_configuration_skips_all() -> None:
    provider = MockImageProvider(fail_with=AIConfigurationError())
    service = ImageService(provider, enabled=True)
    markdown = (
        "![A](IMAGE_PLACEHOLDER_1)\n![B](INFOGRAPHIC_PLACEHOLDER_1)"
    )

    updated, assets = await service.replace_placeholders(
        markdown, topic="Матрас"
    )

    assert "IMAGE_PLACEHOLDER_1" in updated
    assert {item.status for item in assets} == {"skipped"}
