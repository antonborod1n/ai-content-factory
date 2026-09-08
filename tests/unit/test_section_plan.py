"""Unit tests for splitting a brief into per-section writing tasks."""

from app.schemas.ai import ArticleWriteInput
from app.services.ai.section_plan import (
    MIN_SECTION_WORD_COUNT,
    build_section_plans,
    distribute,
)


def test_distribute_spreads_items_evenly() -> None:
    assert distribute(3, 3) == [1, 1, 1]
    assert distribute(4, 3) == [2, 1, 1]
    assert distribute(0, 3) == [0, 0, 0]
    assert distribute(2, 0) == []


def test_no_plans_without_an_outline() -> None:
    request = ArticleWriteInput(topic="Тема")
    assert build_section_plans(request, target_word_count=3000) == []


def test_no_plans_for_a_single_heading() -> None:
    request = ArticleWriteInput(topic="Тема", outline=["Введение"])
    assert build_section_plans(request, target_word_count=3000) == []


def test_plans_split_the_word_budget_across_sections() -> None:
    request = ArticleWriteInput(
        topic="Тема",
        outline=["Раздел 1", "Раздел 2", "  ", "Раздел 3"],
    )
    plans = build_section_plans(request, target_word_count=3000)

    assert [plan.title for plan in plans] == ["Раздел 1", "Раздел 2", "Раздел 3"]
    assert [plan.index for plan in plans] == [1, 2, 3]
    assert all(plan.total == 3 for plan in plans)
    assert all(plan.word_count == 1000 for plan in plans)
    assert [plan.is_last for plan in plans] == [False, False, True]


def test_sections_never_get_a_pointless_word_budget() -> None:
    request = ArticleWriteInput(
        topic="Тема", outline=[f"Раздел {index}" for index in range(10)]
    )
    plans = build_section_plans(request, target_word_count=300)

    assert all(plan.word_count == MIN_SECTION_WORD_COUNT for plan in plans)


def test_placeholder_numbering_is_unique_across_sections() -> None:
    request = ArticleWriteInput(
        topic="Тема",
        outline=["Раздел 1", "Раздел 2", "Раздел 3"],
        image_placeholders=3,
        infographic_placeholders=1,
    )
    plans = build_section_plans(request, target_word_count=3000)

    assert sum(plan.image_placeholders for plan in plans) == 3
    assert sum(plan.infographic_placeholders for plan in plans) == 1
    assert [plan.first_image_number for plan in plans] == [1, 2, 3]
    assert plans[0].first_infographic_number == 1
    # The single infographic belongs to the first section, so later sections
    # would continue from number two if they had one.
    assert [plan.first_infographic_number for plan in plans] == [1, 2, 2]
