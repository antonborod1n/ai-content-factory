"""Tests for saving completed articles to Markdown and HTML files."""

import uuid
from pathlib import Path

from app.core.article_file import (
    HTML_FILENAME,
    MARKDOWN_FILENAME,
    article_dir_name,
    article_output_dir,
    render_article_markdown,
    save_article_to_file,
    slugify_topic,
    try_save_article_to_file,
)
from app.core.markdown_html import markdown_to_html_fragment, render_article_html
from app.db.models.article import Article, ArticleStatus


def _article(**overrides: object) -> Article:
    payload = {
        "id": uuid.uuid4(),
        "topic": "Как выбрать промышленный насос",
        "language": "ru",
        "audience": "Инженеры",
        "keywords": ["насос"],
        "title": "Заголовок статьи",
        "meta_description": "Краткое описание",
        "url_slug": "kak-vybrat-nasos",
        "content_markdown": (
            "# **Заголовок**\n\nТекст статьи.\n\n"
            "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
        ),
        "word_count": 3,
        "status": ArticleStatus.COMPLETED,
        "error_message": None,
    }
    payload.update(overrides)
    return Article(**payload)


def test_slugify_topic_is_filesystem_safe() -> None:
    assert " " not in slugify_topic("Как выбрать насос?")
    assert slugify_topic("!!!") == "article"


def test_save_article_to_file_uses_per_article_folder(tmp_path: Path) -> None:
    article = _article()
    md_path, html_path = save_article_to_file(article, tmp_path)

    article_dir = article_output_dir(tmp_path, article)
    assert article_dir.is_dir()
    assert str(article.id) in article_dir_name(article)
    assert md_path == article_dir / MARKDOWN_FILENAME
    assert html_path == article_dir / HTML_FILENAME

    # Root output dir contains only the article folder, not loose files.
    assert set(tmp_path.iterdir()) == {article_dir}
    assert {p.name for p in article_dir.iterdir()} == {
        MARKDOWN_FILENAME,
        HTML_FILENAME,
    }

    md_text = md_path.read_text(encoding="utf-8")
    assert str(article.id) in md_text
    assert "url_slug: kak-vybrat-nasos" in md_text
    assert "# **Заголовок**" in md_text
    assert md_text.startswith("---\n")

    html_text = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_text
    assert "Заголовок статьи" in html_text
    assert "<table>" in html_text
    assert "<article>" in html_text


def test_try_save_skips_when_output_dir_empty(tmp_path: Path) -> None:
    article = _article()
    assert try_save_article_to_file(article, "") is None
    assert try_save_article_to_file(article, None) is None
    assert list(tmp_path.iterdir()) == []


def test_render_includes_front_matter() -> None:
    article = _article()
    rendered = render_article_markdown(article)
    assert "meta_description: Краткое описание" in rendered
    assert "status: completed" in rendered


def test_markdown_to_html_fragment_handles_headings_and_lists() -> None:
    fragment = markdown_to_html_fragment("## Section\n\n- item\n")
    assert "<h2>" in fragment
    assert "<li>" in fragment


def test_render_article_html_escapes_title() -> None:
    article = _article(title='A <script>alert("x")</script>')
    rendered = render_article_html(article)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
