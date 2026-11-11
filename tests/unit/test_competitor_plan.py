"""Tests for competitor-topics content-plan → topics.json mapping."""

import json
from pathlib import Path

import pytest

from app.core.competitor_plan import (
    import_competitor_plan,
    is_content_plan_payload,
    load_competitor_plan,
    normalize_search_intent,
    plan_to_briefs,
    plan_to_topic_rows,
    plan_topic_to_brief,
)
from app.core.topics_file import load_topics

SAMPLE_PLAN = {
    "domain": "goodnight.by",
    "niche": "товары для сна",
    "audience": "Покупатели матрасов",
    "geo": "Беларусь",
    "siteType": "интернет-магазин",
    "summary": ["ignored extra key"],
    "topics": [
        {
            "title": "Какой матрас выбрать в Беларуси",
            "category": "Выбор матраса",
            "priority": "High",
            "competitors": ["Promatras", "Askona BY"],
            "isGap": False,
            "uniqueAngle": "Хаб с таблицей и FAQ, цены в BYN.",
            "intent": "informational / howto",
            "commercialLink": "Категория матрасов, квиз",
            "format": "гайд",
            "month": None,
        },
        {
            "title": "Что такое шаум в матрасе",
            "category": "Наполнители",
            "priority": "High",
            "competitors": ["gap"],
            "isGap": True,
            "uniqueAngle": "Ключ из файла клиента.",
            "intent": "informational",
            "commercialLink": "Беспружинные",
            "format": "гайд",
            "month": None,
        },
        {
            "title": "Лён или кокос в матрасе",
            "category": "Наполнители",
            "priority": "Low",
            "competitors": ["Mr.Mattress"],
            "isGap": False,
            "uniqueAngle": "",
            "intent": "commercial / compare",
            "commercialLink": "",
            "format": "сравнение",
            "month": None,
        },
    ],
}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", "informational_commercial"),
        ("  ", "informational_commercial"),
        ("informational", "informational"),
        ("informational / howto", "informational_howto"),
        ("commercial / compare", "commercial_compare"),
        ("commercial / transactional", "commercial_transactional"),
    ],
)
def test_normalize_search_intent(raw: str, expected: str) -> None:
    assert normalize_search_intent(raw) == expected


def test_load_and_map_sample_plan(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(SAMPLE_PLAN, ensure_ascii=False), encoding="utf-8")

    plan = load_competitor_plan(path)
    assert plan.domain == "goodnight.by"
    assert plan.audience == "Покупатели матрасов"
    assert len(plan.topics) == 3
    assert plan.topics[1].is_gap is True
    assert plan.topics[1].competitors == []

    briefs = plan_to_briefs(plan)
    assert len(briefs) == 3

    hub = briefs[0]
    assert hub["topic"] == "Какой матрас выбрать в Беларуси"
    assert hub["language"] == "ru"
    assert hub["audience"] == "Покупатели матрасов"
    assert hub["search_intent"] == "informational_howto"
    assert hub["article_goal"] == "Хаб с таблицей и FAQ, цены в BYN."
    assert hub["cta"] == "Категория матрасов, квиз"
    assert hub["keywords"] == ["Какой матрас выбрать в Беларуси"]
    assert hub["use_knowledge_base"] is True
    assert hub["use_competitor_research"] is True
    assert hub["use_dzen"] is False
    assert "outline" not in hub
    assert "word_count" not in hub
    assert "research_id" not in hub
    assert "priority" not in hub
    assert "isGap" not in hub
    assert "competitors" not in hub

    gap = briefs[1]
    assert gap["search_intent"] == "informational"
    assert gap["cta"] == "Беспружинные"

    compare = briefs[2]
    assert compare["search_intent"] == "commercial_compare"
    assert "article_goal" not in compare
    assert "cta" not in compare

    rows = plan_to_topic_rows(plan)
    assert rows[0]["source_competitors"] == ["Promatras", "Askona BY"]
    assert rows[0]["priority"] == "High"
    assert rows[1]["is_gap"] is True
    assert rows[1]["source_engines"] == ["competitor_inventory"]


def test_import_merges_and_skips_duplicates(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(SAMPLE_PLAN, ensure_ascii=False), encoding="utf-8")
    topics_path = tmp_path / "topics.json"
    topics_path.write_text(
        json.dumps(
            [{"topic": "Какой матрас выбрать в Беларуси", "language": "ru"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = import_competitor_plan(plan_path, topics_path)
    assert result.added == 2
    assert result.skipped == 1

    topics = load_topics(topics_path)
    assert [item["topic"] for item in topics] == [
        "Какой матрас выбрать в Беларуси",
        "Что такое шаум в матрасе",
        "Лён или кокос в матрасе",
    ]
    assert topics[1]["use_competitor_research"] is True
    assert "outline" not in topics[1]


def test_load_rejects_empty_topics(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps({"domain": "example.com", "topics": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no topics"):
        load_competitor_plan(path)


def test_load_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps([{"title": "Тема"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        load_competitor_plan(path)


def test_plan_topic_to_brief_uses_plan_audience() -> None:
    from app.core.competitor_plan import CompetitorPlan, CompetitorPlanTopic

    plan = CompetitorPlan(
        audience="Люди, выбирающие товары для сна",
        topics=[
            CompetitorPlanTopic.model_validate(
                {"title": "Как выбрать топпер", "intent": "commercial / howto"}
            )
        ],
    )
    brief = plan_topic_to_brief(plan.topics[0], plan)
    assert brief["audience"] == "Люди, выбирающие товары для сна"
    assert brief["search_intent"] == "commercial_howto"


REAL_PLAN = (
    Path(__file__).resolve().parents[2]
    / "topics"
    / "content-plan-goodnight.by.json"
)


@pytest.mark.skipif(not REAL_PLAN.is_file(), reason="goodnight content plan is not in topics/")
def test_real_goodnight_plan_maps_without_research_fields() -> None:
    plan = load_competitor_plan(REAL_PLAN)
    briefs = plan_to_briefs(plan)
    assert len(briefs) >= 100
    assert plan.domain == "goodnight.by"
    for brief in briefs:
        assert brief["topic"]
        assert brief["use_competitor_research"] is True
        assert "outline" not in brief
        assert "word_count" not in brief
        assert "research_id" not in brief
        assert "priority" not in brief


def test_is_content_plan_payload() -> None:
    assert is_content_plan_payload(SAMPLE_PLAN) is True
    assert is_content_plan_payload({"urls": ["https://example.com/a"]}) is False
    assert is_content_plan_payload({"topics": []}) is False
    assert is_content_plan_payload("nope") is False

