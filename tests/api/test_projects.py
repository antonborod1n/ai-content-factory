"""Projects are isolated: another project's articles and documents stay hidden."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models.project import DEFAULT_PROJECT_ID

pytestmark = pytest.mark.asyncio


async def test_list_includes_default_project(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    slugs = [item["slug"] for item in response.json()]
    assert "default" in slugs


async def test_create_project_rejects_bad_slug(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/projects",
        json={"name": "Bad", "slug": "Has Space", "language": "ru"},
    )
    assert response.status_code == 422


async def test_working_endpoint_requires_project_header(api_app) -> None:
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as bare:
        response = await bare.get("/api/v1/articles")
    assert response.status_code == 422


async def test_default_project_cannot_be_deleted(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/projects/{DEFAULT_PROJECT_ID}")
    assert response.status_code == 409
    listed = await client.get("/api/v1/projects")
    assert "default" in [item["slug"] for item in listed.json()]


async def test_delete_project_removes_only_its_documents(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/projects",
        json={"name": "Temporary", "slug": "temporary-site", "language": "ru"},
    )
    assert created.status_code == 201
    other_id = created.json()["id"]
    ingested = await client.post(
        "/api/v1/documents",
        headers={"X-Project-Id": other_id},
        json={"title": "Чужой", "content": "Текст чужого проекта."},
    )
    assert ingested.status_code == 201

    deleted = await client.delete(f"/api/v1/projects/{other_id}")
    assert deleted.status_code == 204

    listed = await client.get("/api/v1/projects")
    assert other_id not in [item["id"] for item in listed.json()]
    missing = await client.get("/api/v1/documents", headers={"X-Project-Id": other_id})
    assert missing.status_code == 404
    visible = await client.get("/api/v1/documents")
    assert visible.status_code == 200
    assert visible.json()["total"] == 0


async def test_documents_do_not_leak_across_projects(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/projects",
        json={"name": "Other", "slug": "other-site", "language": "en"},
    )
    assert created.status_code == 201
    other_id = created.json()["id"]

    ingested = await client.post(
        "/api/v1/documents",
        json={"title": "Только default", "content": "Текст базы default проекта."},
    )
    assert ingested.status_code == 201

    hidden = await client.get(
        "/api/v1/documents",
        headers={"X-Project-Id": other_id},
    )
    assert hidden.status_code == 200
    assert hidden.json()["total"] == 0

    visible = await client.get(
        "/api/v1/documents",
        headers={"X-Project-Id": str(DEFAULT_PROJECT_ID)},
    )
    assert visible.status_code == 200
    assert visible.json()["total"] == 1
