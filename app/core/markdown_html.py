"""Convert article Markdown to a simple HTML document."""

from __future__ import annotations

import html

import markdown

from app.db.models.article import Article

_MARKDOWN_EXTENSIONS = [
    "markdown.extensions.tables",
    "markdown.extensions.fenced_code",
    "markdown.extensions.nl2br",
    "markdown.extensions.sane_lists",
]


def markdown_to_html_fragment(content_markdown: str) -> str:
    """Convert Markdown body to an HTML fragment (no full document)."""
    return markdown.markdown(
        content_markdown or "",
        extensions=_MARKDOWN_EXTENSIONS,
        output_format="html",
    )


def render_article_html(article: Article) -> str:
    """Full HTML document for a completed article."""
    title = article.title or article.topic
    safe_title = html.escape(title)
    safe_meta = html.escape(article.meta_description or "")
    lang = html.escape(article.language or "ru")
    body = markdown_to_html_fragment(article.content_markdown or "")

    meta_tag = ""
    if safe_meta:
        meta_tag = f'  <meta name="description" content="{safe_meta}">\n'

    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{lang}">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{meta_tag}"
        f"  <title>{safe_title}</title>\n"
        "  <style>\n"
        "    body { font-family: system-ui, sans-serif; line-height: 1.55;"
        " max-width: 48rem; margin: 2rem auto; padding: 0 1rem; }\n"
        "    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }\n"
        "    th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem;"
        " text-align: left; }\n"
        "    img { max-width: 100%; height: auto; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <article>\n{body}\n  </article>\n"
        "</body>\n"
        "</html>\n"
    )
