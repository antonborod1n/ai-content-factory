"""Close jobs left running by a dead process. SQL only."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.article import Article, ArticleStatus
from app.db.models.discovery import ContentPlan, ContentPlanStatus
from app.db.models.document import Document, DocumentStatus
from app.db.models.research import ResearchRun, ResearchStatus
from app.db.models.run import Run, RunStep

_BUSY_ARTICLES = (ArticleStatus.PENDING, ArticleStatus.PROCESSING)
_BUSY_RESEARCH = (ResearchStatus.PENDING, ResearchStatus.PROCESSING)
_BUSY_PLANS = (ContentPlanStatus.PENDING, ContentPlanStatus.PROCESSING)
_BUSY_DOCUMENTS = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)
_MAX_ERROR = 500


def _plan_titles(plan: ContentPlan) -> list[str]:
    titles: list[str] = []
    for topic in plan.topics:
        brief = topic.brief if isinstance(topic.brief, dict) else {}
        title = str(brief.get("topic") or "").strip()
        if title:
            titles.append(title[:500])
        if len(titles) >= 30:
            break
    return titles


@dataclass
class InterruptedWork:
    """Rows closed because no process is still doing them."""

    run_ids: list[uuid.UUID] = field(default_factory=list)
    articles: int = 0
    research: int = 0
    plans: int = 0
    documents: int = 0


class RecoveryRepository:
    """Mark leftover running work failed. Not scoped to one project."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def close_interrupted(self, *, error: str) -> InterruptedWork:
        message = error[:_MAX_ERROR]
        now = datetime.now(UTC)
        runs = list(
            await self._session.scalars(select(Run).where(Run.status == "running"))
        )
        run_ids = [run.id for run in runs]
        if run_ids:
            steps = list(
                await self._session.scalars(
                    select(RunStep).where(
                        RunStep.run_id.in_(run_ids),
                        RunStep.finished_at.is_(None),
                    )
                )
            )
            for step in steps:
                step.status = "failed"
                step.error = message
                step.finished_at = now
            for run in runs:
                started = run.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=UTC)
                run.status = "failed"
                run.error = message
                run.finished_at = now
                run.duration_ms = max(
                    0, int((now - started).total_seconds() * 1000)
                )
        articles = list(
            await self._session.scalars(
                select(Article).where(Article.status.in_(_BUSY_ARTICLES))
            )
        )
        for article in articles:
            article.status = ArticleStatus.FAILED
            article.error_message = message
        research_rows = list(
            await self._session.scalars(
                select(ResearchRun).where(ResearchRun.status.in_(_BUSY_RESEARCH))
            )
        )
        for row in research_rows:
            row.status = ResearchStatus.FAILED
            row.error_message = message
        plans = list(
            await self._session.scalars(
                select(ContentPlan).where(ContentPlan.status.in_(_BUSY_PLANS))
            )
        )
        for plan in plans:
            plan.status = ContentPlanStatus.FAILED
            plan.error_message = message
        documents = list(
            await self._session.scalars(
                select(Document).where(Document.status.in_(_BUSY_DOCUMENTS))
            )
        )
        for document in documents:
            document.status = DocumentStatus.FAILED
            document.error_message = message
        await self._session.commit()
        return InterruptedWork(
            run_ids=run_ids,
            articles=len(articles),
            research=len(research_rows),
            plans=len(plans),
            documents=len(documents),
        )

    async def backfill_plan_runs(self) -> list[uuid.UUID]:
        """Add history rows for topic plans saved before history tracked them."""
        plans = list(
            await self._session.scalars(
                select(ContentPlan)
                .where(ContentPlan.status == ContentPlanStatus.COMPLETED)
                .options(selectinload(ContentPlan.topics))
            )
        )
        if not plans:
            return []
        existing = list(
            await self._session.scalars(
                select(Run).where(
                    Run.task_type.in_(
                        ("discovery", "competitor_topics", "competitor_plan")
                    )
                )
            )
        )
        known = {
            str(run.input_json.get("plan_id"))
            for run in existing
            if isinstance(run.input_json, dict) and run.input_json.get("plan_id")
        }
        created: list[uuid.UUID] = []
        for plan in plans:
            if str(plan.id) in known:
                continue
            titles = _plan_titles(plan)
            started = plan.created_at
            finished = plan.updated_at or started
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=UTC)
            run_id = uuid.uuid4()
            self._session.add(
                Run(
                    id=run_id,
                    project_id=plan.project_id,
                    task_type=(
                        "discovery"
                        if plan.source == "serp"
                        else "competitor_topics"
                    ),
                    status="completed",
                    input_json={
                        "plan_id": str(plan.id),
                        "niche": plan.niche,
                        "seeds": list(plan.seeds)[:20],
                        "language": plan.language,
                        "audience": plan.audience,
                    },
                    output_json={
                        "plan_id": str(plan.id),
                        "topics": len(plan.topics),
                        "titles": titles,
                    },
                    started_at=started,
                    finished_at=finished,
                    duration_ms=max(
                        0, int((finished - started).total_seconds() * 1000)
                    ),
                )
            )
            created.append(run_id)
        if created:
            await self._session.commit()
        return created
