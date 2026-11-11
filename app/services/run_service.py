"""Read execution history for one project."""

from __future__ import annotations

import uuid

from app.core.exceptions import RunNotFoundError
from app.db.models.run import Run
from app.repositories.run_repository import RunRepository


class RunService:
    """List and fetch runs. Writing happens through RunTracker."""

    def __init__(self, repository: RunRepository) -> None:
        self._repository = repository

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        task_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Run], int]:
        return await self._repository.list(
            limit=limit,
            offset=offset,
            task_type=task_type,
            status=status,
        )

    async def get(self, run_id: uuid.UUID) -> Run:
        run = await self._repository.get_by_id(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run

    async def list_active(self) -> list[Run]:
        return await self._repository.list_active()
