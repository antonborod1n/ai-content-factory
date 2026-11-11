"""Tests for saving completed articles to Markdown and HTML files."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.article_file import (
    COMPETITORS_FILENAME,
    DZEN_HTML_FILENAME,
    DZEN_MARKDOWN_FILENAME,
    GENERATE_JSON_FILENAME,
    HTML_FILENAME,
    MARKDOWN_FILENAME,
    RESEARCH_FILENAME,
    RESEARCH_JSON_FILENAME,
    SUMMARY_MARKDOWN_FILENAME,
    article_dir_name,
    article_output_dir,
    render_article_markdown,
    resolve_article_media_path,
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
        "created_at": datetime(2026, 9, 8, 9, 0, tzinfo=UTC),
    }
    payload.update(overrides)
    return Article(**payload)


def test_slugify_topic_is_filesystem_safe() -> None:
    assert " " not in slugify_topic("Как выбрать насос?")
    assert slugify_topic("!!!") == "article"


def test_article_dir_name_starts_with_day_month_year() -> None:
    article = _article()
    name = article_dir_name(article)
    expected_slug = slugify_topic(article.topic)
    assert name == f"08-09-2026-{article.id}_{expected_slug}"


def test_article_dir_name_uses_today_when_created_at_is_missing() -> None:
    article = _article()
    article.created_at = None  # type: ignore[assignment]
    today = datetime.now(UTC).strftime("%d-%m-%Y")
    assert article_dir_name(article).startswith(f"{today}-{article.id}_")


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
        GENERATE_JSON_FILENAME,
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
    assert "class=\"toc\"" not in html_text


def test_save_article_writes_image_files(tmp_path: Path) -> None:
    article = _article()
    save_article_to_file(
        article,
        tmp_path,
        image_files=[("images/image-1.png", b"png-bytes")],
    )
    dest = article_output_dir(tmp_path, article) / "images" / "image-1.png"
    assert dest.read_bytes() == b"png-bytes"


def test_save_article_skips_path_traversal(tmp_path: Path) -> None:
    article = _article()
    save_article_to_file(
        article,
        tmp_path,
        image_files=[("../escape.png", b"x"), ("images/ok.png", b"ok")],
    )
    article_dir = article_output_dir(tmp_path, article)
    assert not (tmp_path / "escape.png").exists()
    assert (article_dir / "images" / "ok.png").read_bytes() == b"ok"


def test_resolve_article_media_path_returns_image(tmp_path: Path) -> None:
    article = _article()
    save_article_to_file(
        article,
        tmp_path,
        image_files=[("images/cover.png", b"cover")],
    )
    path = resolve_article_media_path(tmp_path, article, "images/cover.png")
    assert path is not None
    assert path.read_bytes() == b"cover"


def test_resolve_article_media_path_blocks_escape(tmp_path: Path) -> None:
    article = _article()
    save_article_to_file(article, tmp_path, image_files=[("images/ok.png", b"ok")])
    assert resolve_article_media_path(tmp_path, article, "../ok.png") is None
    assert resolve_article_media_path(tmp_path, article, "article.md") is None
    assert resolve_article_media_path("", article, "images/ok.png") is None


def test_save_article_writes_dzen_files(tmp_path: Path) -> None:
    article = _article(
        dzen={
            "status": "completed",
            "title": "Короткий матрас",
            "content_markdown": "![Главная](images/dzen-cover.png)\n\nТекст.",
            "char_count": 12,
            "assets": [],
        }
    )
    save_article_to_file(article, tmp_path)
    article_dir = article_output_dir(tmp_path, article)
    md = (article_dir / DZEN_MARKDOWN_FILENAME).read_text(encoding="utf-8")
    html = (article_dir / DZEN_HTML_FILENAME).read_text(encoding="utf-8")
    assert "channel: dzen" in md
    assert "Короткий матрас" in md
    assert "<!DOCTYPE html>" in html
    assert "Короткий матрас" in html


def test_save_article_writes_summary_file(tmp_path: Path) -> None:
    article = _article(
        quality={
            "detectors": {"status": "completed", "verdict": "pass"},
            "summary": {
                "status": "completed",
                "text": "Кратко о матрасе.",
                "char_count": 17,
            },
        }
    )
    save_article_to_file(article, tmp_path)
    article_dir = article_output_dir(tmp_path, article)
    md = (article_dir / SUMMARY_MARKDOWN_FILENAME).read_text(encoding="utf-8")
    assert "kind: summary" in md
    assert "Кратко о матрасе." in md
    front = render_article_markdown(article)
    assert "summary: Кратко о матрасе." in front


def test_try_save_skips_when_output_dir_empty(tmp_path: Path) -> None:
    article = _article()
    assert try_save_article_to_file(article, "") is None
    assert try_save_article_to_file(article, None) is None
    assert list(tmp_path.iterdir()) == []


def test_render_includes_competitor_urls() -> None:
    article = _article(
        competitor_sources=[
            {
                "rank": 1,
                "title": "Жесткий матрас",
                "url": "https://example.com/firm-mattress",
            },
            {
                "rank": 2,
                "title": "Мягкий матрас",
                "url": "https://example.com/soft-mattress",
            },
        ]
    )
    rendered = render_article_markdown(article)
    assert "## Проанализированные конкуренты" in rendered
    assert "https://example.com/firm-mattress" in rendered
    assert "https://example.com/soft-mattress" in rendered
    assert rendered.index("# **Заголовок**") < rendered.index(
        "## Проанализированные конкуренты"
    )


def test_save_article_writes_competitor_files(tmp_path: Path) -> None:
    article = _article(
        competitor_sources=[
            {
                "rank": 1,
                "title": "Жесткий матрас",
                "url": "https://example.com/firm-mattress",
            },
            {
                "rank": 2,
                "title": "Мягкий матрас",
                "url": "https://example.com/soft-mattress",
            },
        ]
    )
    save_article_to_file(
        article,
        tmp_path,
        outline=["Для кого жесткий матрас", "FAQ"],
        research_payload={
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "topic": article.topic,
            "competitors": [
                {
                    "rank": 1,
                    "title": "Жесткий матрас",
                    "url": "https://example.com/firm-mattress",
                }
            ],
        },
    )
    article_dir = article_output_dir(tmp_path, article)
    links = (article_dir / COMPETITORS_FILENAME).read_text(encoding="utf-8")
    assert links.splitlines() == [
        "https://example.com/firm-mattress",
        "https://example.com/soft-mattress",
    ]
    research_note = (article_dir / RESEARCH_FILENAME).read_text(encoding="utf-8")
    assert "## План статьи" in research_note
    assert "- Для кого жесткий матрас" in research_note
    assert "https://example.com/firm-mattress" in research_note
    html = (article_dir / HTML_FILENAME).read_text(encoding="utf-8")
    assert "https://example.com/firm-mattress" not in html
    generate = json.loads(
        (article_dir / GENERATE_JSON_FILENAME).read_text(encoding="utf-8")
    )
    assert generate["id"] == str(article.id)
    assert generate["content_markdown"].startswith("# **Заголовок**")
    research_json = json.loads(
        (article_dir / RESEARCH_JSON_FILENAME).read_text(encoding="utf-8")
    )
    assert research_json["id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert research_json["competitors"][0]["url"] == (
        "https://example.com/firm-mattress"
    )


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
