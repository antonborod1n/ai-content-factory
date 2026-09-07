"""Unit tests for prompt loading."""

from pathlib import Path

import pytest

from app.config import get_settings
from app.core.exceptions import AIConfigurationError
from app.services.ai.prompt_loader import (
    get_prompts_dir,
    load_prompt,
    load_system_prompt,
    render_article_writer_prompt,
)


def test_load_article_writer_prompt() -> None:
    content = load_prompt("article_writer.md")
    assert "{{topic}}" in content
    assert "content_markdown" in content


def test_render_article_writer_prompt_substitutes_fields() -> None:
    rendered = render_article_writer_prompt(
        topic="Pump guide",
        language="ru",
        audience="Buyers",
        keywords=["nasos", "vybor"],
        target_word_count=1500,
    )
    assert "Pump guide" in rendered
    assert "ru" in rendered
    assert "Buyers" in rendered
    assert "nasos, vybor" in rendered
    assert "1500" in rendered
    assert "{{" not in rendered


def test_render_uses_target_word_count_from_settings() -> None:
    rendered = render_article_writer_prompt(
        topic="Topic",
        language="ru",
        audience="general",
        keywords=[],
    )
    expected = str(get_settings().article_target_word_count)
    assert expected in rendered
    assert "{{target_word_count}}" not in rendered


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
    (tmp_path / "article_writer.md").write_text("custom {{topic}}", encoding="utf-8")
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        assert get_prompts_dir() == tmp_path
        assert load_prompt("article_writer.md") == "custom {{topic}}"
    finally:
        get_settings.cache_clear()


def test_prompts_dir_never_resolves_into_site_packages() -> None:
    assert "site-packages" not in str(get_prompts_dir())
