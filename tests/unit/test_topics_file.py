"""Tests for topics file parsing (no API / OpenAI calls)."""

import json
from pathlib import Path

import pytest

from app.core.topics_file import load_topics

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


def test_example_and_working_files_in_repo_are_valid() -> None:
    paths = [
        ROOT / "topics" / "topics.json",
        * (ROOT / "topics").glob("topics.example.*"),
    ]
    assert paths
    for path in paths:
        if not path.is_file():
            continue
        topics = load_topics(path)
        assert topics
        assert all(item["topic"] for item in topics)
