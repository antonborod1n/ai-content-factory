"""Task-run history for article, image, and competitor jobs."""

import json
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ai_writer
from app.config import get_settings
from app.db.models.project import DEFAULT_PROJECT_ID
from app.repositories.run_repository import RunRepository
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.services.ai.mock_writer import MockAIWriter

pytestmark = pytest.mark.asyncio

RUNS = "/api/v1/runs"
SECRET = "sk-run-history-must-hide"


class ExplodingWriter:
    async def generate(self, request: ArticleWriteInput) -> AIArticleOutput:
        raise RuntimeError(f"postgresql://acf:{SECRET}@db/acf unreachable")


async def _generate(api_app: FastAPI, client: AsyncClient) -> dict:
    api_app.dependency_overrides[get_ai_writer] = lambda: MockAIWriter()
    response = await client.post(
        "/api/v1/articles/generate",
        json={"topic": "Как выбрать жесткость матраса", "language": "ru"},
    )
    assert response.status_code == 200
    return response.json()


async def test_article_generate_records_run_and_steps(
    api_app: FastAPI, client: AsyncClient
) -> None:
    article = await _generate(api_app, client)
    listed = await client.get(RUNS)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["task_type"] == "article"
    assert item["status"] == "completed"
    assert item["input_json"]["article_id"] == article["id"]
    assert item["output_json"]["word_count"] == article["word_count"]
    assert "content_markdown" not in json.dumps(item["input_json"])
    assert "content_markdown" not in json.dumps(item["output_json"])
    assert isinstance(item["duration_ms"], int)
    names = [step["step"] for step in item["steps"]]
    assert names == [
        "research",
        "knowledge",
        "writer",
        "images",
        "links",
        "quality",
        "dzen",
        "save",
    ]
    by_name = {step["step"]: step["status"] for step in item["steps"]}
    assert by_name["writer"] == "completed"
    assert by_name["save"] == "completed"
    assert by_name["images"] == "skipped"
    assert by_name["research"] == "skipped"

    detail = await client.get(f"{RUNS}/{item['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == item["id"]
    assert len(detail.json()["steps"]) == 8

    raw = Path(get_settings().runs_log_path).read_text(encoding="utf-8")
    assert item["id"] in raw
    assert article["content_markdown"] not in raw
    line = next(
        json.loads(row)
        for row in raw.splitlines()
        if item["id"] in row and '"run_finished"' in row
    )
    assert set(line) == {
        "timestamp",
        "level",
        "run_id",
        "step",
        "event",
        "status",
        "error",
    }


async def test_failed_generate_hides_the_exception(
    api_app: FastAPI, client: AsyncClient
) -> None:
    api_app.dependency_overrides[get_ai_writer] = lambda: ExplodingWriter()
    response = await client.post(
        "/api/v1/articles/generate",
        json={"topic": "Секрет не должен попасть в журнал"},
    )
    assert response.status_code == 500
    listed = await client.get(RUNS)
    item = listed.json()["items"][0]
    assert item["status"] == "failed"
    assert SECRET not in json.dumps(item)
    writer = next(step for step in item["steps"] if step["step"] == "writer")
    assert writer["status"] == "failed"
    assert writer["error"] == "failed"


async def test_image_and_competitor_runs(api_app: FastAPI, client: AsyncClient) -> None:
    article = await _generate(api_app, client)
    images = await client.post(f"/api/v1/articles/{article['id']}/images")
    assert images.status_code == 200
    research = await client.post(
        "/api/v1/research",
        json={"topic": "Ортопедический матрас"},
    )
    assert research.status_code == 201

    listed = await client.get(RUNS)
    kinds = [item["task_type"] for item in listed.json()["items"]]
    assert kinds.count("article") == 1
    assert kinds.count("images") == 1
    assert kinds.count("competitor") == 1

    competitor = next(
        item for item in listed.json()["items"] if item["task_type"] == "competitor"
    )
    assert [step["step"] for step in competitor["steps"]] == [
        "search",
        "fetch",
        "outline",
    ]
    assert competitor["output_json"]["research_id"] == research.json()["id"]
    assert "content_markdown" not in json.dumps(competitor)


async def test_active_runs_and_missing_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    missing = await client.get(f"{RUNS}/{uuid.uuid4()}")
    assert missing.status_code == 404

    empty = await client.get(f"{RUNS}/active")
    assert empty.status_code == 200
    assert empty.json()["total"] == 0

    repository = RunRepository(db_session, project_id=DEFAULT_PROJECT_ID)
    run = await repository.create(task_type="article", input_json={"topic": "ещё идёт"})
    active = await client.get(f"{RUNS}/active")
    assert active.status_code == 200
    assert active.json()["total"] == 1
    assert active.json()["items"][0]["id"] == str(run.id)
    assert active.json()["items"][0]["status"] == "running"


async def test_runs_stay_inside_the_project(
    api_app: FastAPI, client: AsyncClient
) -> None:
    await _generate(api_app, client)
    created = await client.post(
        "/api/v1/projects",
        json={"name": "Другой", "slug": "other-runs", "language": "ru"},
    )
    assert created.status_code == 201
    other_id = created.json()["id"]
    hidden = await client.get(RUNS, headers={"X-Project-Id": other_id})
    assert hidden.status_code == 200
    assert hidden.json()["total"] == 0

    research = await client.post(
        "/api/v1/research",
        headers={"X-Project-Id": other_id},
        json={"topic": "Чужой разбор"},
    )
    assert research.status_code == 201
    visible = await client.get(RUNS, headers={"X-Project-Id": other_id})
    assert visible.json()["total"] == 1
    assert visible.json()["items"][0]["task_type"] == "competitor"

    deleted = await client.delete(f"/api/v1/projects/{other_id}")
    assert deleted.status_code == 204
    gone = await client.get(RUNS, headers={"X-Project-Id": other_id})
    assert gone.status_code == 404
