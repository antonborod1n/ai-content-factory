"""Unit tests for AI schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.ai import AIArticleOutput, ArticleWriteInput


def test_article_write_input_defaults() -> None:
    payload = ArticleWriteInput(topic="Pumps")
    assert payload.language == "ru"
    assert payload.audience == "general"
    assert payload.keywords == []
    assert payload.primary_keywords == []
    assert payload.word_count is None


def test_article_write_input_syncs_keywords() -> None:
    from_legacy = ArticleWriteInput(topic="T", keywords=["a", "b"])
    assert from_legacy.primary_keywords == ["a", "b"]

    from_primary = ArticleWriteInput(topic="T", primary_keywords=["x"])
    assert from_primary.keywords == ["x"]
    assert from_primary.keywords_for_storage() == ["x"]


def test_article_write_input_merges_keywords_for_storage() -> None:
    payload = ArticleWriteInput(
        topic="T",
        primary_keywords=["a", "b"],
        secondary_keywords=["b", "c"],
    )
    assert payload.keywords_for_storage() == ["a", "b", "c"]


def test_brief_for_prompt_uses_default_word_count() -> None:
    payload = ArticleWriteInput(
        topic="Как выбрать промышленный насос",
        primary_keywords=["промышленный насос"],
        outline=["Введение"],
    )
    brief = payload.brief_for_prompt(default_word_count=3000)
    assert brief["word_count"] == 3000
    assert brief["topic"] == "Как выбрать промышленный насос"
    assert brief["outline"] == ["Введение"]


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
