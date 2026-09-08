"""Unit tests for prompt loading."""

from pathlib import Path

import pytest

from app.config import get_settings
from app.core.exceptions import AIConfigurationError
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.services.ai.prompt_loader import (
    get_prompts_dir,
    load_prompt,
    load_system_prompt,
    render_article_expand_prompt,
    render_article_writer_prompt,
    words_per_section,
)


def test_load_article_writer_prompt() -> None:
    content = load_prompt("article_writer.md")
    assert "{{brief_json}}" in content
    assert "{{word_count}}" in content
    assert "content_markdown" in content


def test_render_article_writer_prompt_substitutes_brief() -> None:
    request = ArticleWriteInput(
        topic="Как выбрать промышленный насос",
        language="ru",
        audience="Инженеры и закупщики",
        word_count=3000,
        primary_keywords=["промышленный насос", "как выбрать насос"],
        secondary_keywords=["напор насоса"],
        article_goal="Практическое руководство",
        tone="экспертный, разговорный",
        outline=["Введение", "FAQ", "Заключение"],
        cta="Обратитесь за подбором",
    )
    rendered = render_article_writer_prompt(request, default_word_count=1800)

    assert "Как выбрать промышленный насос" in rendered
    assert "3000" in rendered
    assert "Инженеры и закупщики" in rendered
    assert "промышленный насос" in rendered
    assert "напор насоса" in rendered
    assert "Практическое руководство" in rendered
    assert "Обратитесь за подбором" in rendered
    assert '"outline"' in rendered
    assert "{{" not in rendered


def test_render_uses_default_word_count_from_settings() -> None:
    rendered = render_article_writer_prompt(
        ArticleWriteInput(topic="Тема"),
    )
    expected = str(get_settings().article_target_word_count)
    assert expected in rendered
    assert "{{word_count}}" not in rendered


def test_writer_prompt_states_a_per_section_word_budget() -> None:
    request = ArticleWriteInput(
        topic="Тема",
        word_count=3000,
        outline=["Раздел 1", "Раздел 2", "Раздел 3"],
    )
    rendered = render_article_writer_prompt(request, default_word_count=1800)

    assert words_per_section(request, 3000) == 1000
    assert "1000" in rendered
    assert "{{" not in rendered


def test_words_per_section_falls_back_without_outline() -> None:
    request = ArticleWriteInput(topic="Тема")
    assert words_per_section(request, 3000) == 500


def test_render_article_expand_prompt_includes_the_current_draft() -> None:
    request = ArticleWriteInput(topic="Тема", word_count=3000)
    current = AIArticleOutput(
        title="Заголовок",
        meta_description="Описание",
        url_slug="zagolovok",
        content_markdown="# Заголовок\n\nКороткий черновик.",
        word_count=4,
    )
    rendered = render_article_expand_prompt(
        request,
        current=current,
        current_word_count=4,
        default_word_count=1800,
    )

    assert "Короткий черновик." in rendered
    assert "Заголовок" in rendered
    assert "zagolovok" in rendered
    assert "3000" in rendered
    assert "{{" not in rendered


def test_system_prompt_is_loaded_from_file() -> None:
    system_prompt = load_system_prompt()
    assert "JSON" in system_prompt
    assert system_prompt == system_prompt.strip()


def test_load_prompt_missing_file_is_safe_error(tmp_path: Path) -> None:
    with pytest.raises(AIConfigurationError, match="Prompt file"):
        load_prompt("missing.md", prompts_dir=tmp_path)


def test_prompts_dir_setting_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "article_writer.md").write_text(
        "custom {{topic}} {{brief_json}}", encoding="utf-8"
    )
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        assert get_prompts_dir() == tmp_path
        assert "custom" in load_prompt("article_writer.md")
    finally:
        get_settings.cache_clear()


def test_prompts_dir_never_resolves_into_site_packages() -> None:
    assert "site-packages" not in str(get_prompts_dir())
