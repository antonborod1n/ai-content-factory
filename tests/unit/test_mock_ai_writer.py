"""Unit tests for MockAIWriter."""

import pytest

from app.core.exceptions import AIProviderError, AIValidationError
from app.schemas.ai import ArticleWriteInput
from app.services.ai.mock_writer import MockAIWriter


@pytest.mark.asyncio
async def test_mock_ai_writer_is_deterministic() -> None:
    writer = MockAIWriter()
    request = ArticleWriteInput(
        topic="Industrial pumps",
        language="en",
        audience="Engineers",
        keywords=["pump", "selection"],
    )

    first = await writer.generate(request)
    second = await writer.generate(request)

    assert first == second
    assert first.title == "Mock: Industrial pumps"
    assert "Industrial pumps" in first.content_markdown
    assert "Engineers" in first.content_markdown
    assert "pump" in first.content_markdown
    assert first.word_count > 0
    assert len(writer.calls) == 2


@pytest.mark.asyncio
async def test_mock_ai_writer_can_raise_provider_error() -> None:
    writer = MockAIWriter(fail_with=AIProviderError())
    with pytest.raises(AIProviderError):
        await writer.generate(ArticleWriteInput(topic="Topic"))


@pytest.mark.asyncio
async def test_mock_ai_writer_invalid_payload_raises_validation_error() -> None:
    writer = MockAIWriter(invalid_payload={"title": "Only title"})
    with pytest.raises(AIValidationError, match="validation"):
        await writer.generate(ArticleWriteInput(topic="Topic"))
