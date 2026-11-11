"""Operator settings: project edit, runtime status without secrets, prompt text."""

import pytest
from httpx import AsyncClient

from app.config import get_settings

pytestmark = pytest.mark.asyncio


async def test_patch_project_updates_name_and_language(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/projects",
        json={"name": "Старое", "slug": "settings-site", "language": "ru"},
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Новое", "domain": "example.com", "language": "en"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "Новое"
    assert body["domain"] == "example.com"
    assert body["language"] == "en"
    assert body["slug"] == "settings-site"


async def test_runtime_status_hides_secrets(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/runtime")
    assert response.status_code == 200
    body = response.json()
    assert "openai_configured" in body
    assert "openai_model" in body
    text = response.text
    assert "api_key" not in text
    settings = get_settings()
    if settings.openai_api_key:
        assert settings.openai_api_key not in text
    if settings.serp_api_key:
        assert settings.serp_api_key not in text


async def test_prompts_are_readable_and_path_escape_is_rejected(
    client: AsyncClient,
) -> None:
    listed = await client.get("/api/v1/prompts")
    assert listed.status_code == 200
    names = [item["filename"] for item in listed.json()]
    assert "article_writer.md" in names

    detail = await client.get("/api/v1/prompts/article_writer.md")
    assert detail.status_code == 200
    assert "language" in detail.json()["content"]

    escaped = await client.get("/api/v1/prompts/..%2F.env")
    assert escaped.status_code == 404
