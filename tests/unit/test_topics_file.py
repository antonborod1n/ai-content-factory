"""Tests for topics file parsing (no API / OpenAI calls)."""

import json
from pathlib import Path

import pytest

from app.core.topics_file import (
    apply_content_flags,
    apply_use_dzen,
    dump_topic_brief,
    load_topics,
    merge_topics,
)
from app.schemas.articles import ArticleGenerateRequest

ROOT = Path(__file__).resolve().parents[2]


def test_load_json_brief_objects(tmp_path: Path) -> None:
    path = tmp_path / "topics.json"
    path.write_text(
        json.dumps(
            [
                {
                    "topic": "Тема A",
                    "language": "ru",
                    "audience": "Инженеры",
                    "word_count": 3000,
                    "primary_keywords": ["насос"],
                    "secondary_keywords": ["напор"],
                    "outline": ["Введение", "FAQ"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    topics = load_topics(path)

    assert len(topics) == 1
    assert topics[0]["topic"] == "Тема A"
    assert topics[0]["word_count"] == 3000
    assert topics[0]["primary_keywords"] == ["насос"]
    assert topics[0]["secondary_keywords"] == ["напор"]
    assert topics[0]["outline"] == ["Введение", "FAQ"]
    assert topics[0]["keywords"] == ["насос"]
    assert topics[0]["use_dzen"] is False


def test_load_json_keeps_use_dzen(tmp_path: Path) -> None:
    path = tmp_path / "topics.json"
    path.write_text(
        json.dumps([{"topic": "Тема A", "use_dzen": True}], ensure_ascii=False),
        encoding="utf-8",
    )
    assert load_topics(path)[0]["use_dzen"] is True


def test_apply_content_flags() -> None:
    payload = {"topic": "Тема A", "use_text": True, "use_images": True}
    assert apply_content_flags(payload) is payload
    text_only = apply_content_flags(payload, text_only=True)
    assert text_only["use_text"] is True
    assert text_only["use_images"] is False
    images_only = apply_content_flags(
        payload, images_only=True, article_id="abc"
    )
    assert images_only["use_text"] is False
    assert images_only["use_images"] is True
    assert images_only["article_id"] == "abc"


def test_apply_use_dzen_override() -> None:
    payload = {"topic": "Тема A", "use_dzen": True}
    assert apply_use_dzen(payload, None) is payload
    assert apply_use_dzen(payload, False)["use_dzen"] is False
    assert apply_use_dzen(payload, True)["use_dzen"] is True
    assert payload["use_dzen"] is True


def test_load_json_legacy_keywords(tmp_path: Path) -> None:
    path = tmp_path / "topics.json"
    path.write_text(
        json.dumps(
            [
                {
                    "topic": "Тема A",
                    "keywords": ["насос", ""],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    topics = load_topics(path)
    assert topics[0]["keywords"] == ["насос"]
    assert topics[0]["primary_keywords"] == ["насос"]


def test_load_json_strings(tmp_path: Path) -> None:
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(["Первая", "Вторая"]), encoding="utf-8")

    assert load_topics(path) == [{"topic": "Первая"}, {"topic": "Вторая"}]


def test_load_txt_skips_comments_and_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "topics.txt"
    path.write_text(
        "# comment\n\nТема 1\n  Тема 2  \n# another\n",
        encoding="utf-8",
    )

    assert load_topics(path) == [{"topic": "Тема 1"}, {"topic": "Тема 2"}]


def test_load_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "topics.txt"
    path.write_text("# only comments\n\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no topics"):
        load_topics(path)


def test_working_topics_file_has_use_dzen_toggle() -> None:
    topics = load_topics(ROOT / "topics" / "topics.json")
    assert "use_dzen" in topics[0]


def test_dump_omits_research_derived_fields() -> None:
    brief = dump_topic_brief(
        ArticleGenerateRequest(
            topic="Тема A",
            use_competitor_research=True,
            word_count=3000,
            outline=["Введение", "FAQ"],
            include_tables=True,
            image_placeholders=3,
        )
    )
    assert brief["topic"] == "Тема A"
    assert brief["use_competitor_research"] is True
    assert brief["use_knowledge_base"] is True
    assert "word_count" not in brief
    assert "outline" not in brief
    assert "image_placeholders" not in brief
    assert "include_tables" not in brief


def test_dump_keeps_explicit_research_fields() -> None:
    source = {
        "topic": "Тема A",
        "use_competitor_research": True,
        "word_count": 1500,
        "outline": ["Введение", "FAQ"],
        "include_tables": False,
        "image_placeholders": 4,
    }
    brief = dump_topic_brief(
        ArticleGenerateRequest.model_validate(source),
        source=source,
    )
    assert brief["word_count"] == 1500
    assert brief["outline"] == ["Введение", "FAQ"]
    assert brief["include_tables"] is False
    assert brief["image_placeholders"] == 4


def test_research_linked_topics_keep_analysis_fields(tmp_path: Path) -> None:
    source = {
        "topic": "Тема с разбором",
        "research_id": "11111111-1111-1111-1111-111111111111",
        "use_competitor_research": True,
        "use_dzen": False,
        "word_count": 2500,
        "outline": ["Введение", "Критерии", "FAQ"],
        "image_placeholders": 3,
        "include_faq": True,
    }
    brief = dump_topic_brief(
        ArticleGenerateRequest.model_validate(source),
        source=source,
    )
    path = tmp_path / "topics.json"
    path.write_text(json.dumps([brief], ensure_ascii=False), encoding="utf-8")

    item = load_topics(path)[0]
    assert item["research_id"] == source["research_id"]
    assert item["use_competitor_research"] is True
    assert "use_dzen" in item
    assert item["word_count"] == 2500
    assert item["outline"] == source["outline"]
    assert item["image_placeholders"] == 3
    assert item["include_faq"] is True


def test_merge_topics_appends_and_skips_existing(tmp_path: Path) -> None:
    path = tmp_path / "topics.json"
    path.write_text(
        json.dumps([{"topic": "Тема A", "language": "ru"}], ensure_ascii=False),
        encoding="utf-8",
    )
    result = merge_topics(
        path,
        [
            {"topic": "тема a"},
            {
                "topic": "Тема B",
                "primary_keywords": ["ключ"],
                "outline": ["Введение"],
            },
        ],
    )
    assert result.added == 1
    assert result.skipped == 1
    topics = load_topics(path)
    assert [item["topic"] for item in topics] == ["Тема A", "Тема B"]
    assert topics[0]["language"] == "ru"
    assert topics[1]["primary_keywords"] == ["ключ"]


def test_merge_topics_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "topics.json"
    result = merge_topics(path, [{"topic": "Новая тема"}])
    assert result.added == 1
    assert load_topics(path)[0]["topic"] == "Новая тема"


def test_example_files_in_repo_are_valid() -> None:
    paths = sorted((ROOT / "topics").glob("topics.example.*"))
    assert paths
    for path in paths:
        topics = load_topics(path)
        assert topics
        assert all(item["topic"] for item in topics)
