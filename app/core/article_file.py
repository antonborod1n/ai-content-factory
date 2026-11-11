"""Write completed articles to Markdown and HTML files on disk.

Layout::

    output/articles/{DD-MM-YYYY}-{uuid}_{slug}/
      article.md
      article.html
      competitors.txt             # optional, Stage 3 URLs only
      research.md                 # optional, Stage 3 outline + sources
      stage3_research.json        # optional, Stage 3 API research payload
      stage3_generate.json        # generate API payload for this article
      dzen.md                     # optional, Stage 6
      dzen.html                   # optional, Stage 6
      summary.md                  # optional, Stage 6 quality
      images/cover.png            # optional, Stage 5 hero from title
      images/image-1.png          # optional, Stage 5
      images/dzen-cover.png       # optional, Stage 6
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.markdown_html import render_article_html, render_html_document
from app.db.models.article import Article

logger = logging.getLogger(__name__)

_UNSAFE_RE = re.compile(r"[^\w\-]+", re.UNICODE)
_DASHES_RE = re.compile(r"-{2,}")

MARKDOWN_FILENAME = "article.md"
HTML_FILENAME = "article.html"
COMPETITORS_FILENAME = "competitors.txt"
RESEARCH_FILENAME = "research.md"
RESEARCH_JSON_FILENAME = "stage3_research.json"
GENERATE_JSON_FILENAME = "stage3_generate.json"
DZEN_MARKDOWN_FILENAME = "dzen.md"
DZEN_HTML_FILENAME = "dzen.html"
SUMMARY_MARKDOWN_FILENAME = "summary.md"
FOLDER_DATE_FORMAT = "%d-%m-%Y"


def slugify_topic(topic: str, *, max_length: int = 60) -> str:
    """Build a filesystem-safe fragment from the article topic."""
    cleaned = topic.strip().lower().replace(" ", "-")
    cleaned = _UNSAFE_RE.sub("-", cleaned)
    cleaned = _DASHES_RE.sub("-", cleaned).strip("-")
    if not cleaned:
        cleaned = "article"
    return cleaned[:max_length].rstrip("-")


def folder_date_prefix(article: Article) -> str:
    """Calendar date for the folder name, ``DD-MM-YYYY``."""
    created = getattr(article, "created_at", None)
    if created is None:
        created = datetime.now(UTC)
    return created.strftime(FOLDER_DATE_FORMAT)


def article_dir_name(article: Article) -> str:
    """Return ``{DD-MM-YYYY}-{uuid}_{slug}`` folder name for one article."""
    return f"{folder_date_prefix(article)}-{article.id}_{slugify_topic(article.topic)}"


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
    summary_line = ""
    summary_text = _summary_text(article)
    if summary_text:
        collapsed = " ".join(summary_text.split())
        summary_line = f"summary: {collapsed}\n"
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
        f"{summary_line}"
        "---\n\n"
        f"{body.rstrip()}\n"
        f"{_competitor_sources_markdown(article)}"
    )


def save_article_to_file(
    article: Article,
    output_dir: Path | str,
    *,
    image_files: list[tuple[str, bytes]] | None = None,
    outline: list[str] | None = None,
    research_payload: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    """Write Markdown, HTML, and optional image files into a per-article folder.

    Returns ``(md_path, html_path)``.
    """
    article_dir = article_output_dir(output_dir, article)
    article_dir.mkdir(parents=True, exist_ok=True)

    md_path = article_dir / MARKDOWN_FILENAME
    html_path = article_dir / HTML_FILENAME
    md_path.write_text(render_article_markdown(article), encoding="utf-8")
    html_path.write_text(render_article_html(article), encoding="utf-8")
    _write_generate_json(article_dir, article)
    _write_competitor_files(
        article_dir,
        article,
        outline=outline,
        research_payload=research_payload,
    )
    _write_dzen_files(article_dir, article)
    _write_summary_file(article_dir, article)
    _write_image_files(article_dir, image_files)
    logger.info("Saved article %s to %s", article.id, article_dir)
    return md_path, html_path


def _write_dzen_files(article_dir: Path, article: Article) -> None:
    payload = getattr(article, "dzen", None)
    if not isinstance(payload, dict):
        return
    body = str(payload.get("content_markdown") or "").strip()
    if not body:
        return
    title = str(payload.get("title") or article.title or article.topic)
    char_count = payload.get("char_count", "")
    markdown = (
        "---\n"
        "channel: dzen\n"
        f"title: {title}\n"
        f"char_count: {char_count}\n"
        "---\n\n"
        f"{body.rstrip()}\n"
    )
    (article_dir / DZEN_MARKDOWN_FILENAME).write_text(markdown, encoding="utf-8")
    (article_dir / DZEN_HTML_FILENAME).write_text(
        render_html_document(
            title=title,
            content_markdown=body,
            language=article.language or "ru",
        ),
        encoding="utf-8",
    )


def _competitor_sources(article: Article) -> list[tuple[int, str, str]]:
    payload = getattr(article, "competitor_sources", None)
    if not isinstance(payload, list):
        return []
    items: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for raw in payload:
        if isinstance(raw, str):
            url = raw.strip()
            title = ""
            rank = 0
        elif isinstance(raw, dict):
            url = str(raw.get("url") or "").strip()
            title = str(raw.get("title") or "").strip()
            try:
                rank = int(raw.get("rank") or 0)
            except (TypeError, ValueError):
                rank = 0
        else:
            continue
        if not url or url in seen:
            continue
        seen.add(url)
        items.append((rank, title, url))
    items.sort(key=lambda item: (item[0] or 10_000, item[2]))
    return items


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_generate_json(article_dir: Path, article: Article) -> None:
    from app.schemas.articles import article_detail_response

    payload = article_detail_response(article).model_dump(mode="json")
    _write_json_file(article_dir / GENERATE_JSON_FILENAME, payload)


def _write_competitor_files(
    article_dir: Path,
    article: Article,
    *,
    outline: list[str] | None = None,
    research_payload: dict[str, Any] | None = None,
) -> None:
    """Write a URL list, a short research note, and optional research JSON."""
    if research_payload:
        _write_json_file(article_dir / RESEARCH_JSON_FILENAME, research_payload)
    items = _competitor_sources(article)
    if not items:
        return
    urls = [url for _rank, _title, url in items]
    (article_dir / COMPETITORS_FILENAME).write_text(
        "\n".join(urls) + "\n",
        encoding="utf-8",
    )
    lines = ["# Анализ конкурентов", ""]
    headings = [item.strip() for item in (outline or []) if item.strip()]
    if headings:
        lines.append("## План статьи")
        lines.append("")
        lines.extend(f"- {item}" for item in headings)
        lines.append("")
    lines.append("## Ссылки")
    lines.append("")
    for rank, title, url in items:
        prefix = f"{rank}. " if rank else "- "
        if title:
            lines.append(f"{prefix}{title}")
            lines.append(f"   {url}")
        else:
            lines.append(f"{prefix}{url}")
        lines.append("")
    (article_dir / RESEARCH_FILENAME).write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
    )


def _competitor_sources_markdown(article: Article) -> str:
    items = _competitor_sources(article)
    if not items:
        return ""
    lines = ["", "## Проанализированные конкуренты", ""]
    for rank, title, url in items:
        prefix = f"{rank}. " if rank else "- "
        if title:
            lines.append(f"{prefix}{title} — {url}")
        else:
            lines.append(f"{prefix}{url}")
    return "\n".join(lines) + "\n"


def _summary_text(article: Article) -> str:
    payload = getattr(article, "quality", None)
    if not isinstance(payload, dict):
        return ""
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return ""
    if str(summary.get("status") or "") != "completed":
        return ""
    return str(summary.get("text") or "").strip()


def _write_summary_file(article_dir: Path, article: Article) -> None:
    text = _summary_text(article)
    if not text:
        return
    payload = article.quality if isinstance(article.quality, dict) else {}
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    char_count = ""
    if isinstance(summary, dict):
        char_count = summary.get("char_count", "")
    markdown = (
        "---\n"
        "kind: summary\n"
        f"char_count: {char_count}\n"
        "---\n\n"
        f"{text.rstrip()}\n"
    )
    (article_dir / SUMMARY_MARKDOWN_FILENAME).write_text(markdown, encoding="utf-8")


def resolve_article_media_path(
    output_dir: Path | str | None,
    article: Article,
    relative: str,
) -> Path | None:
    """Return a file under the article folder, or None if missing/unsafe."""
    if output_dir is None:
        return None
    cleaned_root = str(output_dir).strip()
    if not cleaned_root:
        return None
    cleaned = str(relative).replace("\\", "/").lstrip("/")
    if not cleaned or ".." in Path(cleaned).parts:
        return None
    # Operator UI only needs the images/ tree from the article folder.
    if not cleaned.startswith("images/"):
        return None
    article_dir = article_output_dir(cleaned_root, article).resolve()
    candidate = (article_dir / cleaned).resolve()
    if candidate != article_dir and article_dir not in candidate.parents:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _write_image_files(
    article_dir: Path, image_files: list[tuple[str, bytes]] | None
) -> None:
    if not image_files:
        return
    root = article_dir.resolve()
    for relative, payload in image_files:
        cleaned = str(relative).replace("\\", "/").lstrip("/")
        if not cleaned or ".." in Path(cleaned).parts:
            continue
        dest = (article_dir / cleaned).resolve()
        if dest != root and root not in dest.parents:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)


def try_save_article_to_file(
    article: Article,
    output_dir: Path | str | None,
    *,
    image_files: list[tuple[str, bytes]] | None = None,
    outline: list[str] | None = None,
    research_payload: dict[str, Any] | None = None,
) -> tuple[Path, Path] | None:
    """Save when ``output_dir`` is set; log and return None on failure."""
    if output_dir is None:
        return None
    cleaned = str(output_dir).strip()
    if not cleaned:
        return None
    try:
        return save_article_to_file(
            article,
            cleaned,
            image_files=image_files,
            outline=outline,
            research_payload=research_payload,
        )
    except OSError:
        logger.exception(
            "Could not save article %s to %s", article.id, cleaned
        )
        return None
