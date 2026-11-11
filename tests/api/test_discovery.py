"""API tests for Topic Discovery."""

import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.topics_file import load_topics
from app.db.models.discovery import ContentPlanStatus

DISCOVERY = "/api/v1/discovery"


@pytest.mark.asyncio
async def test_create_discovery_returns_briefs(client: AsyncClient) -> None:
    response = await client.post(
        DISCOVERY,
        json={"seeds": ["жесткость матраса"], "niche": "матрасы"},
    )
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["status"] == ContentPlanStatus.COMPLETED.value
    assert body["topics"]
    assert body["topics"][0]["brief"]["topic"]
    assert "google" in body["engines_used"]

    runs = await client.get("/api/v1/runs")
    assert runs.status_code == 200
    discovery_runs = [
        item for item in runs.json()["items"] if item["task_type"] == "discovery"
    ]
    assert discovery_runs
    assert discovery_runs[0]["status"] == "completed"
    assert discovery_runs[0]["output_json"]["plan_id"] == body["id"]
    assert discovery_runs[0]["output_json"]["topics"] >= 1


@pytest.mark.asyncio
async def test_list_and_get_discovery(client: AsyncClient) -> None:
    created = await client.post(DISCOVERY, json={"seeds": ["матрас"]})
    plan_id = created.json()["id"]

    listed = await client.get(DISCOVERY)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    detail = await client.get(f"{DISCOVERY}/{plan_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == plan_id


@pytest.mark.asyncio
async def test_get_discovery_404(client: AsyncClient) -> None:
    response = await client.get(f"{DISCOVERY}/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_discovery_rejects_blank_seeds(client: AsyncClient) -> None:
    response = await client.post(DISCOVERY, json={"seeds": ["  "]})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_export_writes_topics_file(
    client: AsyncClient, tmp_path: Path
) -> None:
    created = await client.post(DISCOVERY, json={"seeds": ["матрас"]})
    plan_id = created.json()["id"]
    dest = tmp_path / "topics.json"
    dest.write_text("[]\n", encoding="utf-8")

    response = await client.post(
        f"{DISCOVERY}/{plan_id}/export",
        json={"path": str(dest)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["added"] >= 1
    topics = load_topics(dest)
    assert topics
    assert all(item["topic"] for item in topics)
    json.loads(dest.read_text(encoding="utf-8"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/etc/acf-escape.json", "../../acf-escape.json", "topics.txt"],
)
async def test_export_rejects_paths_outside_topics_dir(
    client: AsyncClient, path: str
) -> None:
    created = await client.post(DISCOVERY, json={"seeds": ["матрас"]})
    plan_id = created.json()["id"]

    response = await client.post(
        f"{DISCOVERY}/{plan_id}/export",
        json={"path": path},
    )

    assert response.status_code == 422
    assert not Path(path).exists()
