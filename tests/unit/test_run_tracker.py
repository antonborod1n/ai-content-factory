"""Run history stays out of the generation path and out of secrets."""

import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest

from app.core.exceptions import INTERRUPTED_MESSAGE, ArticleGenerationError
from app.core.run_log import append_run_log
from app.services.run_tracker import RunTracker

SECRET = "sk-must-not-appear"


class MemoryRuns:
    def __init__(self, *, fail_create: bool = False) -> None:
        self.fail_create = fail_create
        self.runs: list[SimpleNamespace] = []
        self.steps: list[SimpleNamespace] = []
        self.finished: list[dict[str, object]] = []
        self.rolled_back = False

    async def create(self, *, task_type: str, input_json: dict) -> SimpleNamespace:
        if self.fail_create:
            raise RuntimeError(SECRET)
        run = SimpleNamespace(
            id=uuid.uuid4(), task_type=task_type, input_json=input_json
        )
        self.runs.append(run)
        return run

    async def start_step(self, run_id: uuid.UUID, step: str, *, attempt: int = 1):
        row = SimpleNamespace(
            id=uuid.uuid4(),
            run_id=run_id,
            step=step,
            attempt=attempt,
            status="running",
            error=None,
        )
        self.steps.append(row)
        return row

    async def finish_step(
        self,
        step_id: uuid.UUID,
        *,
        status: str,
        error: str | None,
        detail: dict | None = None,
    ) -> None:
        for row in self.steps:
            if row.id == step_id:
                row.status = status
                row.error = error
                row.detail = detail

    async def finish(
        self,
        run_id: uuid.UUID,
        *,
        status: str,
        output_json: dict | None,
        error: str | None,
    ) -> None:
        self.finished.append(
            {
                "run_id": run_id,
                "status": status,
                "output_json": output_json,
                "error": error,
            }
        )

    async def rollback(self) -> None:
        self.rolled_back = True


def test_append_run_log_writes_one_json_object(tmp_path) -> None:
    path = tmp_path / "nested" / "runs.jsonl"
    append_run_log(
        path,
        {
            "level": "info",
            "run_id": "abc",
            "step": "writer",
            "event": "step_finished",
            "status": "completed",
            "error": None,
        },
    )
    line = json.loads(path.read_text(encoding="utf-8"))
    assert set(line) == {
        "timestamp",
        "level",
        "run_id",
        "step",
        "event",
        "status",
        "error",
    }
    assert line["event"] == "step_finished"
    assert line["step"] == "writer"


@pytest.mark.asyncio
async def test_tracker_drops_secrets_and_hides_unexpected_errors(tmp_path) -> None:
    repository = MemoryRuns()
    log_path = tmp_path / "runs.jsonl"
    tracker = RunTracker(repository, log_path=str(log_path))
    run_id = await tracker.start(
        "article",
        {"topic": "Матрас", "api_key": SECRET, "password": SECRET},
    )
    assert run_id is not None
    assert repository.runs[0].input_json["topic"] == "Матрас"
    assert repository.runs[0].input_json["api_key"] is None
    assert repository.runs[0].input_json["password"] is None

    with pytest.raises(RuntimeError):
        async with tracker.step(run_id, "writer"):
            raise RuntimeError(f"postgresql://acf:{SECRET}@db/acf")

    assert repository.steps[0].status == "failed"
    assert repository.steps[0].error == "failed"
    raw = log_path.read_text(encoding="utf-8")
    assert SECRET not in raw
    assert "content_markdown" not in raw
    events = [json.loads(line)["event"] for line in raw.splitlines()]
    assert events == ["run_started", "step_started", "step_finished"]


@pytest.mark.asyncio
async def test_tracker_records_app_error_and_skipped_step(tmp_path) -> None:
    repository = MemoryRuns()
    tracker = RunTracker(repository, log_path=str(tmp_path / "runs.jsonl"))
    run_id = await tracker.start("images", {"article_id": "1"})
    async with tracker.step(run_id, "images") as handle:
        handle.skip()
        handle.detail = {"api_key": SECRET, "completed": 2}
    with pytest.raises(ArticleGenerationError):
        async with tracker.step(run_id, "save"):
            raise ArticleGenerationError("Article has no markdown to illustrate")
    assert [row.status for row in repository.steps] == ["skipped", "failed"]
    assert repository.steps[0].detail == {"api_key": None, "completed": 2}
    assert repository.steps[1].error == "Article has no markdown to illustrate"


@pytest.mark.asyncio
async def test_tracker_closes_a_cancelled_step(tmp_path) -> None:
    repository = MemoryRuns()
    tracker = RunTracker(repository, log_path=str(tmp_path / "runs.jsonl"))
    run_id = await tracker.start("article", {"topic": "Матрас"})
    with pytest.raises(asyncio.CancelledError):
        async with tracker.step(run_id, "writer"):
            raise asyncio.CancelledError()
    assert repository.steps[0].status == "failed"
    assert repository.steps[0].error == INTERRUPTED_MESSAGE

    with pytest.raises(asyncio.CancelledError):
        try:
            raise asyncio.CancelledError()
        finally:
            await tracker.finish_current(run_id)
    assert repository.finished[0]["status"] == "failed"
    assert repository.finished[0]["error"] == INTERRUPTED_MESSAGE


@pytest.mark.asyncio
async def test_tracker_create_failure_does_not_raise(tmp_path) -> None:
    repository = MemoryRuns(fail_create=True)
    tracker = RunTracker(repository, log_path=str(tmp_path / "runs.jsonl"))
    assert await tracker.start("article", {"topic": "t"}) is None
    assert repository.rolled_back is True
    log_file = tmp_path / "runs.jsonl"
    if log_file.exists():
        assert SECRET not in log_file.read_text(encoding="utf-8")
