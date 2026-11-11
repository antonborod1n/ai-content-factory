"""Persistence for topic-discovery content plans."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.discovery import ContentPlan, ContentPlanStatus, ContentPlanTopic
from app.db.models.project import DEFAULT_PROJECT_ID


class DiscoveryRepository:
    """Database access for content_plans and content_plan_topics."""

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
        niche: str = "",
        seeds: list[str] | None = None,
        language: str = "ru",
        audience: str = "general",
        status: ContentPlanStatus = ContentPlanStatus.PENDING,
        source: str = "serp",
        context: dict | None = None,
    ) -> ContentPlan:
        plan = ContentPlan(
            project_id=self._project_id,
            niche=niche,
            seeds=list(seeds or []),
            language=language,
            audience=audience,
            status=status,
            source=source,
            context=dict(context or {}),
        )
        self._session.add(plan)
        await self._session.commit()
        await self._session.refresh(plan)
        return plan

    async def get_by_id(self, plan_id: uuid.UUID) -> ContentPlan | None:
        result = await self._session.execute(
            select(ContentPlan)
            .options(selectinload(ContentPlan.topics))
            .execution_options(populate_existing=True)
            .where(ContentPlan.id == plan_id)
            .where(ContentPlan.project_id == self._project_id)
        )
        return result.scalar_one_or_none()

    async def update(self, plan_id: uuid.UUID, **fields: Any) -> ContentPlan | None:
        plan = await self.get_by_id(plan_id)
        if plan is None:
            return None
        for key, value in fields.items():
            if not hasattr(plan, key):
                msg = f"Unknown content plan field: {key}"
                raise ValueError(msg)
            setattr(plan, key, value)
        await self._session.commit()
        return await self.get_by_id(plan_id)

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        source: str | None = None,
    ) -> list[ContentPlan]:
        statement = (
            select(ContentPlan)
            .options(selectinload(ContentPlan.topics))
            .where(ContentPlan.project_id == self._project_id)
            .order_by(ContentPlan.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if source is not None:
            statement = statement.where(ContentPlan.source == source)
        result = await self._session.execute(statement)
        return list(result.scalars().unique().all())

    async def count(self, *, source: str | None = None) -> int:
        statement = (
            select(func.count())
            .select_from(ContentPlan)
            .where(ContentPlan.project_id == self._project_id)
        )
        if source is not None:
            statement = statement.where(ContentPlan.source == source)
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def add_topics(
        self,
        plan_id: uuid.UUID,
        rows: list[dict[str, Any]],
    ) -> list[ContentPlanTopic]:
        created: list[ContentPlanTopic] = []
        for row in rows:
            topic = ContentPlanTopic(plan_id=plan_id, **row)
            self._session.add(topic)
            created.append(topic)
        await self._session.commit()
        for topic in created:
            await self._session.refresh(topic)
        return created
