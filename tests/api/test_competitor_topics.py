"""API tests for competitor-inventory content plans."""

import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.core.topics_file import load_topics
from app.db.models.discovery import ContentPlanSource, ContentPlanStatus

ENDPOINT = "/api/v1/competitor-topics"

SAMPLE = {
    "domain": "goodnight.by",
    "audience": "Покупатели матрасов",
    "geo": "Беларусь",
    "siteType": "интернет-магазин",
    "topics": [
        {
            "title": "Какой матрас выбрать в Беларуси",
            "category": "Выбор матраса",
            "priority": "High",
            "competitors": ["Promatras", "Askona BY"],
            "isGap": False,
            "uniqueAngle": "Хаб с FAQ, цены в BYN.",
            "intent": "informational / howto",
            "commercialLink": "Категория матрасов, квиз",
        }
    ],
}


@pytest.mark.asyncio
async def test_import_returns_briefs(client: AsyncClient) -> None:
    response = await client.post(ENDPOINT, json=SAMPLE)
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["status"] == ContentPlanStatus.COMPLETED.value
    assert body["source"] == ContentPlanSource.COMPETITOR_GAP.value
    assert body["context"]["domain"] == "goodnight.by"
    assert body["topics"][0]["brief"]["topic"] == SAMPLE["topics"][0]["title"]
    assert body["topics"][0]["brief"]["search_intent"] == "informational_howto"
    assert not body["topics"][0]["brief"].get("outline")
    assert body["topics"][0]["source_competitors"] == ["Promatras", "Askona BY"]
    assert body["topics"][0]["is_gap"] is False


@pytest.mark.asyncio
async def test_upload_json_file(client: AsyncClient) -> None:
    payload = json.dumps(SAMPLE, ensure_ascii=False).encode("utf-8")
    response = await client.post(
        f"{ENDPOINT}/upload",
        files={"file": ("plan.json", payload, "application/json")},
    )
    assert response.status_code == 201
    assert response.json()["topics"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "field"), [("/upload", "file"), ("/sources", "files")]
)
async def test_upload_rejects_files_over_the_limit(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, path: str, field: str
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    oversized = b"a" * (1024 * 1024 + 1)

    response = await client.post(
        f"{ENDPOINT}{path}",
        files={field: ("dump.csv", oversized, "text/csv")},
    )

    assert response.status_code == 413
    assert "1 MB" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_and_get(client: AsyncClient) -> None:
    created = await client.post(ENDPOINT, json=SAMPLE)
    plan_id = created.json()["id"]

    listed = await client.get(ENDPOINT)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    detail = await client.get(f"{ENDPOINT}/{plan_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == plan_id


@pytest.mark.asyncio
async def test_get_404(client: AsyncClient) -> None:
    response = await client.get(f"{ENDPOINT}/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rejects_empty_topics(client: AsyncClient) -> None:
    response = await client.post(ENDPOINT, json={"domain": "example.com", "topics": []})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_discovery_list_excludes_competitor_plans(client: AsyncClient) -> None:
    imported = await client.post(ENDPOINT, json=SAMPLE)
    assert imported.status_code == 201
    listed = await client.get("/api/v1/discovery")
    assert listed.status_code == 200
    assert listed.json()["total"] == 0


@pytest.mark.asyncio
async def test_export_writes_topics_file(
    client: AsyncClient, tmp_path: Path
) -> None:
    created = await client.post(ENDPOINT, json=SAMPLE)
    plan_id = created.json()["id"]
    dest = tmp_path / "topics.json"

    response = await client.post(
        f"{ENDPOINT}/{plan_id}/export",
        json={"path": str(dest)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["added"] == 1
    topics = load_topics(dest)
    assert topics[0]["topic"] == SAMPLE["topics"][0]["title"]
    assert topics[0]["use_competitor_research"] is True
    assert "outline" not in topics[0]
    json.loads(dest.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_sources_csv_returns_briefs(client: AsyncClient) -> None:
    response = await client.post(
        f"{ENDPOINT}/sources",
        data={
            "domain": "goodnight.by",
            "niche": "товары для сна",
            "audience": "Покупатели матрасов",
            "geo": "Беларусь",
        },
        files=[
            (
                "files",
                (
                    "promatras.csv",
                    "keyword\nкакой матрас выбрать\n".encode("utf-8"),
                    "text/csv",
                ),
            )
        ],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["source"] == ContentPlanSource.COMPETITOR_GAP.value
    assert body["topics"][0]["brief"]["topic"] == "какой матрас выбрать"
    assert not body["topics"][0]["brief"].get("outline")


@pytest.mark.asyncio
async def test_sources_ready_json_skips_gap_analysis(client: AsyncClient) -> None:
    payload = json.dumps(SAMPLE, ensure_ascii=False).encode("utf-8")
    response = await client.post(
        f"{ENDPOINT}/sources",
        data={"domain": "goodnight.by"},
        files=[("files", ("plan.json", payload, "application/json"))],
    )
    assert response.status_code == 201
    assert response.json()["topics"][0]["brief"]["topic"] == SAMPLE["topics"][0]["title"]


@pytest.mark.asyncio
async def test_sources_rejects_unsupported_type(client: AsyncClient) -> None:
    response = await client.post(
        f"{ENDPOINT}/sources",
        files=[("files", ("dump.pdf", b"%PDF-1.4", "application/pdf"))],
    )
    assert response.status_code == 422
    assert "Unsupported" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sources_rejects_service_urls_only(client: AsyncClient) -> None:
    response = await client.post(
        f"{ENDPOINT}/sources",
        files=[
            ("files", ("askona.txt", b"https://askona.by/catalog\n", "text/plain"))
        ],
    )
    assert response.status_code == 422
