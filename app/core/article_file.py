"""Write completed articles to Markdown and HTML files on disk.

Layout::

    output/articles/{uuid}_{slug}/
      article.md
      article.html
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.core.markdown_html import render_article_html
from app.db.models.article import Article

logger = logging.getLogger(__name__)

_UNSAFE_RE = re.compile(r"[^\w\-]+", re.UNICODE)
_DASHES_RE = re.compile(r"-{2,}")

MARKDOWN_FILENAME = "article.md"
HTML_FILENAME = "article.html"


def slugify_topic(topic: str, *, max_length: int = 60) -> str:
    """Build a filesystem-safe fragment from the article topic."""
    cleaned = topic.strip().lower().replace(" ", "-")
    cleaned = _UNSAFE_RE.sub("-", cleaned)
    cleaned = _DASHES_RE.sub("-", cleaned).strip("-")
    if not cleaned:
        cleaned = "article"
    return cleaned[:max_length].rstrip("-")


def article_dir_name(article: Article) -> str:
    """Return ``{uuid}_{slug}`` folder name for one article."""
    return f"{article.id}_{slugify_topic(article.topic)}"


def article_output_dir(output_dir: Path | str, article: Article) -> Path:
    """Return the per-article directory under ``output_dir``."""
    return Path(output_dir) / article_dir_name(article)


def article_filename(_article: Article) -> str:
    """Markdown filename inside the article folder."""
    return MARKDOWN_FILENAME


def article_html_filename(_article: Article) -> str:
    """HTML filename inside the article folder."""
    return HTML_FILENAME


def render_article_markdown(article: Article) -> str:
    """Markdown file body: YAML front matter + content."""
    title = article.title or article.topic
    meta = article.meta_description or ""
    word_count = article.word_count if article.word_count is not None else ""
    body = article.content_markdown or ""
    return (
        "---\n"
        f"id: {article.id}\n"
        f"title: {title}\n"
        f"topic: {article.topic}\n"
        f"url_slug: {article.url_slug or ''}\n"
        f"language: {article.language}\n"
        f"audience: {article.audience}\n"
        f"word_count: {word_count}\n"
        f"status: {article.status.value}\n"
        f"meta_description: {meta}\n"
        "---\n\n"
        f"{body.rstrip()}\n"
    )


def save_article_to_file(
    article: Article,
    output_dir: Path | str,
) -> tuple[Path, Path]:
    """Write Markdown and HTML into a per-article folder.

    Returns ``(md_path, html_path)``.
    """
    article_dir = article_output_dir(output_dir, article)
    article_dir.mkdir(parents=True, exist_ok=True)

    md_path = article_dir / MARKDOWN_FILENAME
    html_path = article_dir / HTML_FILENAME
    md_path.write_text(render_article_markdown(article), encoding="utf-8")
    html_path.write_text(render_article_html(article), encoding="utf-8")
    logger.info("Saved article %s to %s", article.id, article_dir)
    return md_path, html_path


def try_save_article_to_file(
    article: Article,
    output_dir: Path | str | None,
) -> tuple[Path, Path] | None:
    """Save when ``output_dir`` is set; log and return None on failure."""
    if output_dir is None:
        return None
    cleaned = str(output_dir).strip()
    if not cleaned:
        return None
    try:
        return save_article_to_file(article, cleaned)
    except OSError:
        logger.exception(
            "Could not save article %s to %s", article.id, cleaned
        )
        return None
