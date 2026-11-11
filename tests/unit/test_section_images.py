"""Average competitor photos mapped onto our outline headings."""

from app.core.section_images import allocate_section_images, heading_similarity


def test_heading_similarity_overlaps_related_titles() -> None:
    score = heading_similarity(
        "Жесткий матрас для спины", "Для кого жесткий матрас"
    )
    assert score > 0.2
    assert heading_similarity("FAQ", "Заключение") == 0.0


def test_allocate_uses_matched_heading_averages() -> None:
    outline = ["Жесткий матрас", "Мягкий матрас", "FAQ"]
    pages = [
        [("Жесткий матрас", 2), ("Мягкий матрас", 0), ("FAQ", 1)],
        [("Жесткий матрас", 2), ("Мягкий матрас", 0), ("FAQ", 1)],
    ]
    counts = allocate_section_images(outline, pages)
    assert counts == [2, 0, 1]


def test_allocate_returns_empty_when_competitors_have_no_photos() -> None:
    outline = ["Введение", "FAQ"]
    pages = [[("Введение", 0), ("FAQ", 0)]]
    assert allocate_section_images(outline, pages, page_totals=[0]) == []


def test_allocate_fills_unmatched_from_page_average() -> None:
    outline = ["Вес покупателя", "Поза сна", "Заключение"]
    pages = [
        [("Вес и поза", 1), ("Как выбрать", 1)],
        [("Вес покупателя", 1)],
    ]
    counts = allocate_section_images(outline, pages, page_totals=[2, 1])
    assert len(counts) == 3
    assert sum(counts) >= 1
    assert all(item <= 2 for item in counts)
