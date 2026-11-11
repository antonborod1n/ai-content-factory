"""Persistence for client projects."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectNotFoundError, ProjectProtectedError
from app.db.models.article import Article
from app.db.models.discovery import ContentPlan
from app.db.models.document import Document
from app.db.models.project import DEFAULT_PROJECT_ID, DEFAULT_PROJECT_SLUG, Project
from app.db.models.research import ResearchRun
from app.db.models.run import Run


class ProjectRepository:
    """Database access for the projects table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        slug: str,
        domain: str | None = None,
        language: str = "ru",
    ) -> Project:
        project = Project(
            name=name,
            slug=slug,
            domain=domain or None,
            language=language,
        )
        self._session.add(project)
        await self._session.commit()
        await self._session.refresh(project)
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def get_by_slug(self, slug: str) -> Project | None:
        result = await self._session.execute(
            select(Project).where(Project.slug == slug)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        project_id: uuid.UUID,
        *,
        name: str,
        domain: str | None,
        language: str,
    ) -> Project | None:
        project = await self.get_by_id(project_id)
        if project is None:
            return None
        project.name = name
        project.domain = domain
        project.language = language
        await self._session.commit()
        await self._session.refresh(project)
        return project

    async def delete(self, project_id: uuid.UUID) -> str:
        """Remove a project and the rows that belong only to it. Returns its slug."""
        project = await self.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if project.id == DEFAULT_PROJECT_ID or project.slug == DEFAULT_PROJECT_SLUG:
            raise ProjectProtectedError("The default project cannot be deleted")
        slug = project.slug
        await self._session.execute(delete(Article).where(Article.project_id == project_id))
        await self._session.execute(delete(Document).where(Document.project_id == project_id))
        await self._session.execute(
            delete(ResearchRun).where(ResearchRun.project_id == project_id)
        )
        await self._session.execute(
            delete(ContentPlan).where(ContentPlan.project_id == project_id)
        )
        await self._session.execute(delete(Run).where(Run.project_id == project_id))
        await self._session.delete(project)
        await self._session.commit()
        return slug

    async def list(self) -> list[Project]:
        result = await self._session.execute(
            select(Project).order_by(Project.created_at.asc())
        )
        return list(result.scalars().all())
