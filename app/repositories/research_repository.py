"""Persistence for competitor research runs."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.project import DEFAULT_PROJECT_ID
from app.db.models.research import ResearchCompetitor, ResearchRun, ResearchStatus


class ResearchRepository:
    """Database access for research_runs and research_competitors."""

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
        topic: str,
        language: str = "ru",
        audience: str = "general",
        query: str = "",
        status: ResearchStatus = ResearchStatus.PENDING,
    ) -> ResearchRun:
        run = ResearchRun(
            project_id=self._project_id,
            topic=topic,
            language=language,
            audience=audience,
            query=query,
            status=status,
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def get_by_id(self, research_id: uuid.UUID) -> ResearchRun | None:
        result = await self._session.execute(
            select(ResearchRun)
            .options(selectinload(ResearchRun.competitors))
            .where(ResearchRun.id == research_id)
            .where(ResearchRun.project_id == self._project_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self, research_id: uuid.UUID, **fields: Any
    ) -> ResearchRun | None:
        run = await self.get_by_id(research_id)
        if run is None:
            return None
        for key, value in fields.items():
            if not hasattr(run, key):
                msg = f"Unknown research field: {key}"
                raise ValueError(msg)
            setattr(run, key, value)
        await self._session.commit()
        return await self.get_by_id(research_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[ResearchRun]:
        statement = (
            select(ResearchRun)
            .options(selectinload(ResearchRun.competitors))
            .where(ResearchRun.project_id == self._project_id)
            .order_by(ResearchRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().unique().all())

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(ResearchRun)
            .where(ResearchRun.project_id == self._project_id)
        )
        return int(result.scalar_one())

    async def add_competitors(
        self,
        research_id: uuid.UUID,
        rows: list[dict[str, Any]],
    ) -> list[ResearchCompetitor]:
        created: list[ResearchCompetitor] = []
        for row in rows:
            competitor = ResearchCompetitor(research_id=research_id, **row)
            self._session.add(competitor)
            created.append(competitor)
        await self._session.commit()
        for competitor in created:
            await self._session.refresh(competitor)
        return created
