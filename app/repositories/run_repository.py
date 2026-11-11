"""Persistence for task runs and their steps. No business rules."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import DEFAULT_PROJECT_ID
from app.db.models.run import Run, RunStep

_STEP_STATUSES = {"running", "completed", "failed", "skipped"}
_RUN_STATUSES = {"running", "completed", "failed"}


class RunRepository:
    """Database access for runs and run_steps, scoped to one project."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID | None = None,
    ) -> None:
        self._session = session
        self._project_id = project_id or DEFAULT_PROJECT_ID

    async def create(
        self,
        *,
        task_type: str,
        input_json: dict[str, Any],
    ) -> Run:
        run = Run(
            project_id=self._project_id,
            task_type=task_type,
            status="running",
            input_json=input_json,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def finish(
        self,
        run_id: uuid.UUID,
        *,
        status: str,
        output_json: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        run = await self._get(run_id)
        if run is None or run.finished_at is not None:
            return
        finished = datetime.now(UTC)
        started = run.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        run.status = status if status in _RUN_STATUSES else "failed"
        run.output_json = output_json
        run.error = error
        run.finished_at = finished
        run.duration_ms = max(0, int((finished - started).total_seconds() * 1000))
        await self._session.commit()

    async def start_step(
        self,
        run_id: uuid.UUID,
        step: str,
        *,
        attempt: int = 1,
    ) -> RunStep | None:
        run = await self._get(run_id)
        if run is None:
            return None
        row = RunStep(
            run_id=run_id,
            step=step,
            status="running",
            started_at=datetime.now(UTC),
            attempt=max(1, attempt),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def finish_step(
        self,
        step_id: uuid.UUID,
        *,
        status: str,
        error: str | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        row = await self._session.get(RunStep, step_id)
        if row is None or row.finished_at is not None:
            return
        run = await self._get(row.run_id)
        if run is None:
            return
        row.status = status if status in _STEP_STATUSES else "failed"
        row.error = error
        row.detail_json = detail
        row.finished_at = datetime.now(UTC)
        await self._session.commit()

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        task_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Run], int]:
        filters = [Run.project_id == self._project_id]
        if task_type:
            filters.append(Run.task_type == task_type)
        if status:
            filters.append(Run.status == status)
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(Run).where(*filters)
            )
            or 0
        )
        statement = (
            select(Run)
            .where(*filters)
            .order_by(Run.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all()), total

    async def get_by_id(self, run_id: uuid.UUID) -> Run | None:
        return await self._get(run_id)

    async def list_active(self) -> list[Run]:
        statement = (
            select(Run)
            .where(Run.project_id == self._project_id, Run.status == "running")
            .order_by(Run.started_at.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def rollback(self) -> None:
        await self._session.rollback()

    async def _get(self, run_id: uuid.UUID) -> Run | None:
        run = await self._session.get(Run, run_id)
        if run is None or run.project_id != self._project_id:
            return None
        return run
