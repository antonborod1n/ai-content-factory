"""Convert article Markdown to a simple HTML document."""

from __future__ import annotations

import html
import re

import markdown

from app.db.models.article import Article

_MARKDOWN_EXTENSIONS = [
    "markdown.extensions.tables",
    "markdown.extensions.fenced_code",
    "markdown.extensions.nl2br",
    "markdown.extensions.sane_lists",
]
_H2_RE = re.compile(r"<h2(\s[^>]*)?>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_ID_ATTR_RE = re.compile(r'\bid="([^"]+)"', re.IGNORECASE)
_UNSAFE_ID_RE = re.compile(r"[^\w\-]+", re.UNICODE)
_DASHES_RE = re.compile(r"-{2,}")
_MIN_TOC_HEADINGS = 2


def markdown_to_html_fragment(content_markdown: str) -> str:
    """Convert Markdown body to an HTML fragment (no full document)."""
    return markdown.markdown(
        content_markdown or "",
        extensions=_MARKDOWN_EXTENSIONS,
        output_format="html",
    )


def render_html_document(
    *,
    title: str,
    content_markdown: str,
    language: str = "ru",
    meta_description: str = "",
) -> str:
    """Full HTML document for a markdown article body."""
    safe_title = html.escape(title)
    safe_meta = html.escape(meta_description or "")
    lang = html.escape(language or "ru")
    body = add_table_of_contents(
        markdown_to_html_fragment(content_markdown),
        language=language,
    )

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
        "    .toc {\n"
        "      background: #ffffff;\n"
        "      border: 1px solid #eee;\n"
        "      border-radius: 12px;\n"
        "      padding: 16px 20px;\n"
        "      margin: 24px 0;\n"
        "    }\n"
        "    .toc ul { list-style: none; margin: 8px 0 0; padding: 0; }\n"
        "    .toc li { margin: 4px 0; }\n"
        "    .toc a { color: #5b4ee8; text-decoration: none; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <article>\n{body}\n  </article>\n"
        "</body>\n"
        "</html>\n"
    )


def render_article_html(article: Article) -> str:
    """Full HTML document for a completed article."""
    return render_html_document(
        title=article.title or article.topic,
        content_markdown=article.content_markdown or "",
        language=article.language or "ru",
        meta_description=article.meta_description or "",
    )


def add_table_of_contents(fragment: str, *, language: str = "ru") -> str:
    """Add heading ids and a `.toc` block before the first H2."""
    used: set[str] = set()
    items: list[tuple[str, str]] = []

    def _replace(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        inner = match.group(2)
        label = _visible_text(inner)
        if not label:
            return match.group(0)
        found = _ID_ATTR_RE.search(attrs)
        if found:
            slug = found.group(1)
            used.add(slug)
        else:
            slug = heading_anchor_id(label, used)
            attrs = f'{attrs} id="{html.escape(slug, quote=True)}"'
        items.append((slug, label))
        return f"<h2{attrs}>{inner}</h2>"

    updated = _H2_RE.sub(_replace, fragment or "")
    if len(items) < _MIN_TOC_HEADINGS:
        return updated
    toc = render_toc_html(items, language=language)
    first = re.search(r"<h2\b", updated, re.IGNORECASE)
    if first is None:
        return updated
    return f"{updated[: first.start()]}{toc}{updated[first.start() :]}"


def render_toc_html(
    items: list[tuple[str, str]], *, language: str = "ru"
) -> str:
    """HTML for the contents card. Labels are escaped; ids are already slugs."""
    title = (
        "Contents" if (language or "ru").lower().startswith("en") else "Содержание"
    )
    lines = [
        '<div class="toc">',
        f"    <div><strong>{html.escape(title)}</strong></div>",
        "    <ul>",
    ]
    for slug, label in items:
        href = html.escape(slug, quote=True)
        text = html.escape(label)
        lines.append(f'      <li><a href="#{href}">{text}</a></li>')
    lines.extend(["    </ul>", "  </div>", ""])
    return "\n".join(lines)


def heading_anchor_id(text: str, used: set[str]) -> str:
    """Stable HTML id from a heading. Unique within ``used``."""
    slug = " ".join((text or "").split()).lower().replace(" ", "-")
    slug = _UNSAFE_ID_RE.sub("-", slug)
    slug = _DASHES_RE.sub("-", slug).strip("-")
    if not slug:
        slug = "section"
    slug = slug[:80].rstrip("-") or "section"
    candidate = slug
    index = 2
    while candidate in used:
        candidate = f"{slug}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def _visible_text(inner_html: str) -> str:
    return html.unescape(_TAG_RE.sub("", inner_html or "")).strip()
