"""API shapes for execution history."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.run import Run, RunStep


class RunStepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    step: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    detail_json: dict[str, Any] | None = None
    attempt: int


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    task_type: str
    status: str
    input_json: dict[str, Any] = Field(default_factory=dict)
    output_json: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    steps: list[RunStepResponse] = Field(default_factory=list)


class RunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RunResponse]
    total: int


def run_response(run: Run) -> RunResponse:
    return RunResponse(
        id=run.id,
        project_id=run.project_id,
        task_type=run.task_type,
        status=run.status,
        input_json=dict(run.input_json or {}),
        output_json=dict(run.output_json) if run.output_json is not None else None,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=run.duration_ms,
        steps=[_step_response(step) for step in run.steps],
    )


def _step_response(step: RunStep) -> RunStepResponse:
    return RunStepResponse(
        id=step.id,
        step=step.step,
        status=step.status,
        started_at=step.started_at,
        finished_at=step.finished_at,
        error=step.error,
        detail_json=dict(step.detail_json) if step.detail_json else None,
        attempt=step.attempt,
    )
