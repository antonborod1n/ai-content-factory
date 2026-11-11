"""Tests for image/infographic placeholder parsing."""

from app.core.placeholders import (
    COVER_PATH,
    COVER_TOKEN,
    asset_relative_path,
    ensure_cover_placeholder,
    find_placeholders,
    replace_placeholder,
)


def test_find_placeholders_parses_image_and_infographic() -> None:
    markdown = (
        "Текст\n\n"
        "![Матрас в разрезе](IMAGE_PLACEHOLDER_1)\n\n"
        "![Схема слоев](INFOGRAPHIC_PLACEHOLDER_1)\n"
    )
    found = find_placeholders(markdown)
    assert [item.token for item in found] == [
        "IMAGE_PLACEHOLDER_1",
        "INFOGRAPHIC_PLACEHOLDER_1",
    ]
    assert found[0].kind == "image"
    assert found[0].alt == "Матрас в разрезе"
    assert found[1].kind == "infographic"
    assert found[1].number == 1


def test_find_placeholders_dedupes_tokens() -> None:
    markdown = "![A](IMAGE_PLACEHOLDER_2)\n![A again](IMAGE_PLACEHOLDER_2)"
    found = find_placeholders(markdown)
    assert len(found) == 1
    assert found[0].number == 2


def test_replace_placeholder_keeps_alt() -> None:
    markdown = "![Фото](IMAGE_PLACEHOLDER_1)"
    updated = replace_placeholder(markdown, "IMAGE_PLACEHOLDER_1", "images/image-1.png")
    assert updated == "![Фото](images/image-1.png)"


def test_asset_relative_path() -> None:
    assert asset_relative_path("image", 3) == "images/image-3.png"
    assert asset_relative_path("infographic", 1) == "images/infographic-1.png"
    assert asset_relative_path("hero", 0) == COVER_PATH
    assert asset_relative_path("cover", 0) == "images/dzen-cover.png"
    assert asset_relative_path("dzen", 2) == "images/dzen-2.png"


def test_find_placeholders_includes_existing_image_files() -> None:
    markdown = (
        "![Кровать](images/image-1.png)\n"
        "![Схема](images/infographic-1.png)\n"
    )
    found = find_placeholders(markdown)
    assert [item.token for item in found] == [
        "images/image-1.png",
        "images/infographic-1.png",
    ]
    assert found[0].kind == "image"
    assert found[0].number == 1
    assert found[1].kind == "infographic"


def test_ensure_cover_placeholder_inserts_after_h1() -> None:
    markdown = "# **Жесткий или мягкий матрас**\n\nВступление.\n"
    updated = ensure_cover_placeholder(
        markdown, title="Жесткий или мягкий матрас: какой лучше выбрать?"
    )
    assert COVER_TOKEN in updated
    assert updated.index("# **") < updated.index(COVER_TOKEN)
    assert "Вступление" in updated
    again = ensure_cover_placeholder(updated, title="Другое")
    assert again.count(COVER_TOKEN) == 1


def test_find_cover_placeholder_is_hero() -> None:
    found = find_placeholders("![Главная](COVER_PLACEHOLDER)")
    assert found[0].kind == "hero"
    assert found[0].token == COVER_TOKEN
    found_file = find_placeholders("![Главная](images/cover.png)")
    assert found_file[0].kind == "hero"
    assert found_file[0].token == COVER_PATH


def test_find_placeholders_binds_heading_and_excerpt() -> None:
    markdown = (
        "# **Как выбрать матрас**\n\n"
        "Вступление без кадра.\n\n"
        "## **Жёсткий матрас**\n\n"
        "Жёсткий блок держит поясницу ровно.\n\n"
        "![Кадр](IMAGE_PLACEHOLDER_1)\n\n"
        "## **Мягкий матрас**\n\n"
        "Мягкая модель разгружает плечо.\n\n"
        "![Другой кадр](images/image-2.png)\n"
    )
    found = find_placeholders(markdown)
    assert found[0].heading == "Жёсткий матрас"
    assert "поясницу" in found[0].excerpt
    assert found[1].heading == "Мягкий матрас"
    assert "плечо" in found[1].excerpt


def test_find_dzen_placeholders() -> None:
    markdown = (
        "![Обложка](DZEN_COVER_PLACEHOLDER)\n"
        "![Один](DZEN_IMAGE_PLACEHOLDER_1)\n"
        "![Два](DZEN_IMAGE_PLACEHOLDER_2)\n"
    )
    found = find_placeholders(markdown)
    assert [item.kind for item in found] == ["cover", "dzen", "dzen"]
    assert found[0].token == "DZEN_COVER_PLACEHOLDER"
    assert found[1].number == 1
    assert found[2].number == 2
