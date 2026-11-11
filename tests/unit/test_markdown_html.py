"""HTML document rendering: TOC card and heading anchors."""

from app.core.markdown_html import (
    add_table_of_contents,
    heading_anchor_id,
    markdown_to_html_fragment,
    render_html_document,
    render_toc_html,
)


def test_heading_anchor_id_is_stable_and_unique() -> None:
    used: set[str] = set()
    first = heading_anchor_id("Зачем разбираться в типоразмерах", used)
    second = heading_anchor_id("Зачем разбираться в типоразмерах", used)
    assert first == "зачем-разбираться-в-типоразмерах"
    assert second == "зачем-разбираться-в-типоразмерах-2"


def test_toc_html_matches_template_shape() -> None:
    html = render_toc_html(
        [
            ("intro", "Зачем разбираться в типоразмерах"),
            ("meaning", "Что означают цифры в названиях"),
        ]
    )
    assert '<div class="toc">' in html
    assert "<div><strong>Содержание</strong></div>" in html
    assert '<li><a href="#intro">Зачем разбираться в типоразмерах</a></li>' in html
    assert '<li><a href="#meaning">Что означают цифры в названиях</a></li>' in html


def test_add_table_of_contents_inserts_before_first_h2() -> None:
    fragment = (
        "<h1>Статья</h1>\n"
        "<p>Вступление.</p>\n"
        "<h2>Зачем разбираться</h2>\n"
        "<p>Текст.</p>\n"
        "<h2>Заключение</h2>\n"
    )
    updated = add_table_of_contents(fragment, language="ru")
    assert updated.index('class="toc"') < updated.index("<h2")
    assert 'id="зачем-разбираться"' in updated
    assert 'href="#зачем-разбираться"' in updated
    assert 'href="#заключение"' in updated


def test_add_table_of_contents_skips_single_heading() -> None:
    fragment = "<h1>Статья</h1>\n<h2>Один раздел</h2>\n"
    updated = add_table_of_contents(fragment)
    assert 'class="toc"' not in updated


def test_render_html_document_includes_toc_styles() -> None:
    rendered = render_html_document(
        title="Гид",
        language="ru",
        content_markdown=(
            "# Гид\n\n"
            "Вступление.\n\n"
            "## Зачем разбираться в типоразмерах\n\n"
            "Текст.\n\n"
            "## Заключение\n\n"
            "Итог.\n"
        ),
    )
    assert 'class="toc"' in rendered
    assert "Содержание" in rendered
    assert "border-radius: 12px" in rendered
    assert "background: #ffffff" in rendered
    fragment = markdown_to_html_fragment("## Section\n\n- item\n")
    assert "<h2>" in fragment
    assert "<li>" in fragment
