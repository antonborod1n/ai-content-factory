"""GET /api/v1/topics returns only the current project's topic file."""

import json

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_topics_queue_follows_the_project_file(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(
        json.dumps([{"topic": "Тема из файла", "language": "ru"}]),
        encoding="utf-8",
    )
    monkeypatch.setenv("TOPICS_FILE_PATH", str(topics_file))
    from app.config import get_settings

    get_settings.cache_clear()

    listed = await client.get("/api/v1/topics")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["topic"] == "Тема из файла"

    created = await client.post(
        "/api/v1/projects",
        json={"name": "Другой", "slug": "other-queue", "language": "ru"},
    )
    assert created.status_code == 201
    hidden = await client.get(
        "/api/v1/topics",
        headers={"X-Project-Id": created.json()["id"]},
    )
    assert hidden.status_code == 200
    assert hidden.json() == []


async def test_missing_topics_file_returns_empty_list(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("TOPICS_FILE_PATH", str(tmp_path / "absent.json"))
    from app.config import get_settings

    get_settings.cache_clear()
    response = await client.get("/api/v1/topics")
    assert response.status_code == 200
    assert response.json() == []
