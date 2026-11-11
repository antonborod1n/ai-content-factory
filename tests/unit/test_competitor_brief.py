from app.core.competitor_brief import (
    DEFAULT_FAQ_COUNT,
    CompetitorCounts,
    brief_stats_from_competitors,
)


def test_brief_stats_average_volume_and_majority_flags() -> None:
    stats = brief_stats_from_competitors(
        [
            CompetitorCounts(
                word_count=1200,
                list_count=2,
                table_count=1,
                has_faq=True,
                infographic_count=1,
            ),
            CompetitorCounts(
                word_count=800,
                list_count=1,
                table_count=0,
                has_faq=True,
                infographic_count=0,
            ),
            CompetitorCounts(
                word_count=1000,
                list_count=0,
                table_count=1,
                has_faq=False,
                infographic_count=2,
            ),
        ]
    )
    assert stats.word_count == 1000
    assert stats.include_tables is True
    assert stats.include_lists is True
    assert stats.include_faq is True
    assert stats.faq_count == DEFAULT_FAQ_COUNT
    assert stats.infographic_placeholders == 1


def test_brief_stats_tables_fallback_when_no_infographics() -> None:
    stats = brief_stats_from_competitors(
        [
            CompetitorCounts(word_count=900, table_count=1),
            CompetitorCounts(word_count=1100, table_count=2),
        ]
    )
    assert stats.include_tables is True
    assert stats.infographic_placeholders == 1
    assert stats.include_faq is False
    assert stats.faq_count == 0


def test_brief_stats_empty_pages() -> None:
    stats = brief_stats_from_competitors([])
    assert stats.word_count is None
    assert stats.include_tables is False
    assert stats.infographic_placeholders == 0
