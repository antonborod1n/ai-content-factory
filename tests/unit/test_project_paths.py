"""Topic and output paths stay inside the chosen project slug."""

import json

import pytest

from app.core.project_paths import (
    articles_output_for_slug,
    confined_topics_path,
    read_project_topics,
    remove_project_files,
    topics_file_for_slug,
)
from app.db.models.project import DEFAULT_PROJECT_SLUG


def test_default_project_keeps_configured_topics_file(monkeypatch) -> None:
    monkeypatch.setenv("TOPICS_FILE_PATH", "topics/topics.json")
    from app.config import get_settings

    get_settings.cache_clear()
    assert topics_file_for_slug(DEFAULT_PROJECT_SLUG).as_posix() == "topics/topics.json"


def test_other_project_uses_its_own_topics_folder(monkeypatch) -> None:
    monkeypatch.setenv("TOPICS_FILE_PATH", "topics/topics.json")
    monkeypatch.setenv("TOPICS_DIR", "topics")
    from app.config import get_settings

    get_settings.cache_clear()
    path = topics_file_for_slug("goodnight-by")
    assert path.as_posix() == "topics/goodnight-by/topics.json"


def test_article_output_is_under_the_project_slug(monkeypatch) -> None:
    monkeypatch.setenv("ARTICLES_OUTPUT_DIR", "output/articles")
    from app.config import get_settings

    get_settings.cache_clear()
    assert articles_output_for_slug("other-site") == "output/articles/other-site"


def test_read_topics_uses_only_the_project_file(tmp_path, monkeypatch) -> None:
    default_file = tmp_path / "topics.json"
    default_file.write_text(
        json.dumps([{"topic": "Только default"}]),
        encoding="utf-8",
    )
    monkeypatch.setenv("TOPICS_FILE_PATH", str(default_file))
    from app.config import get_settings

    get_settings.cache_clear()
    assert read_project_topics("default")[0]["topic"] == "Только default"
    assert read_project_topics("other-site") == []


def test_remove_project_files_keeps_default(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARTICLES_OUTPUT_DIR", "output/articles")
    monkeypatch.setenv("TOPICS_DIR", "topics")
    from app.config import get_settings

    get_settings.cache_clear()
    (tmp_path / "topics").mkdir()
    (tmp_path / "topics" / "topics.json").write_text("[]", encoding="utf-8")
    other_topics = tmp_path / "topics" / "other-site"
    other_topics.mkdir()
    (other_topics / "topics.json").write_text("[]", encoding="utf-8")
    (tmp_path / "output" / "articles" / "other-site").mkdir(parents=True)
    (tmp_path / "output" / "articles" / "default").mkdir()

    remove_project_files("default")
    remove_project_files("other-site")

    assert (tmp_path / "topics" / "topics.json").is_file()
    assert (tmp_path / "output" / "articles" / "default").is_dir()
    assert not (tmp_path / "topics" / "other-site").exists()
    assert not (tmp_path / "output" / "articles" / "other-site").exists()


def test_missing_topics_file_is_an_empty_queue(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TOPICS_FILE_PATH", str(tmp_path / "missing.json"))
    from app.config import get_settings

    get_settings.cache_clear()
    assert read_project_topics("default") == []


def test_confined_path_accepts_json_inside_topics_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TOPICS_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()
    target = tmp_path / "site" / "topics.json"
    assert confined_topics_path(str(target)) == target.resolve()


@pytest.mark.parametrize(
    "raw",
    ["../escape.json", "/etc/escape.json", "{root}/topics.txt", "{root}/../x.json"],
)
def test_confined_path_rejects_escape_and_non_json(
    tmp_path, monkeypatch, raw: str
) -> None:
    root = tmp_path / "topics"
    root.mkdir()
    monkeypatch.setenv("TOPICS_DIR", str(root))
    from app.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(ValueError):
        confined_topics_path(raw.format(root=root))
