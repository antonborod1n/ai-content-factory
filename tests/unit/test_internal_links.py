"""Tests for deterministic internal-link insertion."""

from app.core.internal_links import LinkTarget, insert_internal_links, score_target


def test_inserts_link_on_keyword_in_body() -> None:
    markdown = (
        "# Заголовок\n\n"
        "Жесткость матраса зависит от веса.\n"
    )
    updated, inserted = insert_internal_links(
        markdown,
        [
            LinkTarget(
                title="Как выбрать жесткость",
                url_slug="kak-vybrat-zhestkost",
                keywords=("жесткость матраса",),
            )
        ],
        keywords=["жесткость матраса"],
        topic="Матрас",
    )
    assert inserted
    assert inserted[0].url_slug == "kak-vybrat-zhestkost"
    assert inserted[0].anchor == "Жесткость матраса"
    assert "[Жесткость матраса](/kak-vybrat-zhestkost)" in updated


def test_does_not_link_inside_heading() -> None:
    markdown = "# Жесткость матраса\n\nДругой текст без якоря."
    updated, inserted = insert_internal_links(
        markdown,
        [
            LinkTarget(
                title="Жесткость",
                url_slug="zhestkost",
                keywords=("жесткость матраса",),
            )
        ],
        keywords=["жесткость матраса"],
        topic="Матрас",
    )
    assert inserted == []
    assert updated == markdown


def test_skips_existing_markdown_links() -> None:
    markdown = "См. [жесткость матраса](https://example.com) в гиде."
    _updated, inserted = insert_internal_links(
        markdown,
        [
            LinkTarget(
                title="Жесткость",
                url_slug="zhestkost",
                keywords=("жесткость матраса",),
            )
        ],
        keywords=["жесткость матраса"],
        topic="Матрас",
    )
    assert inserted == []


def test_score_requires_overlap() -> None:
    target = LinkTarget(title="Насосы", url_slug="nasosy", keywords=("насос",))
    assert score_target(target, keywords=["матрас"], topic="матрас") == 0
    assert score_target(target, keywords=["насос"], topic="выбор") > 0
