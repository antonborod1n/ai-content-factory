"""Interrupted jobs are closed on startup and left alone once they finish."""

import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import INTERRUPTED_MESSAGE
from app.db.models.article import ArticleStatus
from app.db.models.discovery import ContentPlanStatus
from app.db.models.research import ResearchStatus
from app.repositories.article_repository import ArticleRepository
from app.repositories.discovery_repository import DiscoveryRepository
from app.repositories.research_repository import ResearchRepository
from app.repositories.run_repository import RunRepository
from app.services.recovery_service import recover_interrupted_work

pytestmark = pytest.mark.asyncio


async def test_startup_closes_only_unfinished_work(db_session: AsyncSession) -> None:
    articles = ArticleRepository(db_session)
    research = ResearchRepository(db_session)
    runs = RunRepository(db_session)

    busy = await articles.create(topic="зависшая", status=ArticleStatus.PROCESSING)
    waiting = await articles.create(topic="ожидает", status=ArticleStatus.PENDING)
    done = await articles.create(
        topic="готовая",
        status=ArticleStatus.COMPLETED,
        title="Готово",
        content_markdown="текст",
        word_count=1,
    )
    running = await runs.create(task_type="article", input_json={"topic": "зависшая"})
    await runs.start_step(running.id, "writer")
    finished = await runs.create(task_type="article", input_json={"topic": "готовая"})
    await runs.finish(
        finished.id,
        status="completed",
        output_json={"word_count": 1},
        error=None,
    )
    stuck_research = await research.create(
        topic="конкуренты", status=ResearchStatus.PROCESSING
    )
    done_research = await research.create(
        topic="разобрано", status=ResearchStatus.COMPLETED
    )

    running_id = running.id
    finished_id = finished.id
    busy_id = busy.id
    waiting_id = waiting.id
    done_id = done.id
    stuck_research_id = stuck_research.id
    done_research_id = done_research.id

    first = await recover_interrupted_work()
    assert running_id in first.run_ids
    assert finished_id not in first.run_ids
    assert first.articles == 2
    assert first.research == 1
    assert first.plans == 0
    assert first.documents == 0

    db_session.expire_all()
    busy_after = await articles.get_by_id(busy_id)
    waiting_after = await articles.get_by_id(waiting_id)
    done_after_article = await articles.get_by_id(done_id)
    assert busy_after is not None
    assert busy_after.status == ArticleStatus.FAILED
    assert waiting_after is not None
    assert waiting_after.status == ArticleStatus.FAILED
    assert busy_after.error_message == INTERRUPTED_MESSAGE
    assert done_after_article is not None
    assert done_after_article.status == ArticleStatus.COMPLETED
    assert done_after_article.content_markdown == "текст"

    closed = await runs.get_by_id(running_id)
    assert closed is not None
    assert closed.status == "failed"
    assert closed.error == INTERRUPTED_MESSAGE
    assert closed.finished_at is not None
    assert closed.steps[0].status == "failed"
    assert closed.steps[0].finished_at is not None
    kept = await runs.get_by_id(finished_id)
    assert kept is not None
    assert kept.status == "completed"

    stuck_after = await research.get_by_id(stuck_research_id)
    done_after = await research.get_by_id(done_research_id)
    assert stuck_after is not None
    assert stuck_after.status == ResearchStatus.FAILED
    assert done_after is not None
    assert done_after.status == ResearchStatus.COMPLETED

    second = await recover_interrupted_work()
    assert second.run_ids == []
    assert second.articles == 0
    assert second.research == 0
    assert second.plans == 0
    assert second.documents == 0

    log_path = Path(get_settings().runs_log_path)
    lines = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if str(running_id) in line
    ]
    assert lines[-1]["event"] == "run_finished"
    assert lines[-1]["status"] == "failed"
    assert lines[-1]["error"] == INTERRUPTED_MESSAGE


async def test_saved_topic_plan_appears_in_history(
    db_session: AsyncSession,
) -> None:
    plans = DiscoveryRepository(db_session)
    runs = RunRepository(db_session)
    plan = await plans.create(
        niche="освещение",
        seeds=["светодиодный светильник"],
        status=ContentPlanStatus.COMPLETED,
    )
    plan_id = str(plan.id)
    await plans.add_topics(
        plan.id,
        [
            {
                "sort_order": 0,
                "brief": {"topic": "Как выбрать светильник"},
                "source_engines": ["google"],
                "source_queries": ["светодиодный светильник"],
            }
        ],
    )

    await recover_interrupted_work()
    db_session.expire_all()
    listed, total = await runs.list(task_type="discovery")
    assert total == 1
    assert listed[0].input_json["plan_id"] == plan_id
    assert listed[0].output_json["topics"] == 1
    assert listed[0].status == "completed"

    await recover_interrupted_work()
    db_session.expire_all()
    _again, total_again = await runs.list(task_type="discovery")
    assert total_again == 1
