"""Unit tests for DzenService with MockDzenWriter."""

import pytest

from app.core.exceptions import AIConfigurationError, AIProviderError
from app.services.ai.mock_dzen import MockDzenWriter
from app.services.ai.mock_image import MockImageProvider
from app.services.dzen_service import DzenService
from app.services.image_service import ImageService


def _source() -> dict[str, str]:
    return {
        "source_title": "Как выбрать жесткость матраса",
        "source_markdown": "# Как выбрать жесткость матраса\n\nДлинный гид.",
        "language": "ru",
        "audience": "general",
    }


@pytest.mark.asyncio
async def test_writes_short_article_with_three_placeholders() -> None:
    service = DzenService(MockDzenWriter(), enabled=True, target_char_count=4000)
    result = await service.write(**_source(), use_images=False)

    assert result.article.status == "completed"
    assert result.article.title == "Как выбрать жесткость матраса"
    assert "DZEN_COVER_PLACEHOLDER" in result.article.content_markdown
    assert "DZEN_IMAGE_PLACEHOLDER_1" in result.article.content_markdown
    assert "DZEN_IMAGE_PLACEHOLDER_2" in result.article.content_markdown
    assert result.article.char_count == len(result.article.content_markdown)
    assert result.article.char_count > 0


@pytest.mark.asyncio
async def test_replaces_dzen_placeholders_when_images_on() -> None:
    service = DzenService(
        MockDzenWriter(),
        image_service=ImageService(MockImageProvider(), enabled=True),
        enabled=True,
    )
    result = await service.write(**_source(), use_images=True)

    assert "images/dzen-cover.png" in result.article.content_markdown
    assert "images/dzen-1.png" in result.article.content_markdown
    assert "images/dzen-2.png" in result.article.content_markdown
    assert {item.kind for item in result.assets} == {"cover", "dzen"}
    assert all(item.status == "completed" for item in result.assets)
    assert "data" not in result.article.model_dump()["assets"][0]


@pytest.mark.asyncio
async def test_disabled_skips() -> None:
    writer = MockDzenWriter()
    service = DzenService(writer, enabled=False)
    result = await service.write(**_source(), use_images=False)
    assert result.article.status == "skipped"
    assert writer.calls == []


@pytest.mark.asyncio
async def test_writer_error_does_not_raise() -> None:
    service = DzenService(
        MockDzenWriter(fail_with=AIProviderError()), enabled=True
    )
    result = await service.write(**_source(), use_images=False)
    assert result.article.status == "failed"


@pytest.mark.asyncio
async def test_missing_config_skips() -> None:
    service = DzenService(
        MockDzenWriter(fail_with=AIConfigurationError()), enabled=True
    )
    result = await service.write(**_source(), use_images=False)
    assert result.article.status == "skipped"
