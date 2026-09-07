"""Unit tests for AI schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.ai import AIArticleOutput, ArticleWriteInput


def test_article_write_input_defaults() -> None:
    payload = ArticleWriteInput(topic="Pumps")
    assert payload.language == "ru"
    assert payload.audience == "general"
    assert payload.keywords == []


def test_article_write_input_rejects_empty_topic() -> None:
    with pytest.raises(ValidationError):
        ArticleWriteInput(topic="")


def test_ai_article_output_requires_fields() -> None:
    with pytest.raises(ValidationError):
        AIArticleOutput(
            title="T",
            meta_description="M",
            content_markdown="",
            word_count=0,
        )


def test_ai_article_output_valid() -> None:
    payload = AIArticleOutput(
        title="Title",
        meta_description="Meta",
        content_markdown="# Body",
        word_count=2,
    )
    assert payload.word_count == 2
