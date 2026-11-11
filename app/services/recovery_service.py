"""Close work that cannot still be running in this process."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.core.exceptions import INTERRUPTED_MESSAGE
from app.core.run_log import append_run_log
from app.db.session import get_session_factory
from app.repositories.recovery_repository import InterruptedWork, RecoveryRepository

logger = logging.getLogger(__name__)


async def recover_interrupted_work() -> InterruptedWork:
    """Fail runs, articles, and research left open by a previous process.

    Generation is synchronous and lives in this process. At startup nothing
    is in flight, so a row still marked running or processing will never finish.
    """
    factory = get_session_factory()
    async with factory() as session:
        repository = RecoveryRepository(session)
        work = await repository.close_interrupted(error=INTERRUPTED_MESSAGE)
        backfilled = await repository.backfill_plan_runs()
    settings = get_settings()
    for run_id in work.run_ids:
        append_run_log(
            settings.runs_log_path,
            {
                "level": "error",
                "run_id": str(run_id),
                "step": None,
                "event": "run_finished",
                "status": "failed",
                "error": INTERRUPTED_MESSAGE,
            },
        )
    if backfilled:
        logger.info("Recorded saved topic plans runs=%s", len(backfilled))
    if (
        work.run_ids
        or work.articles
        or work.research
        or work.plans
        or work.documents
    ):
        logger.info(
            "Closed interrupted work runs=%s articles=%s research=%s "
            "plans=%s documents=%s",
            len(work.run_ids),
            work.articles,
            work.research,
            work.plans,
            work.documents,
        )
    return work
