"""Record task runs around existing work. Bookkeeping never fails the job."""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.core.exceptions import INTERRUPTED_MESSAGE, AppError
from app.core.run_log import append_run_log
from app.repositories.run_repository import RunRepository

logger = logging.getLogger(__name__)

_SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "database_url",
    "password",
    "secret",
    "token",
}
_MAX_ERROR = 500


class StepHandle:
    """Lets the caller mark a finished stage skipped or failed without raising."""

    def __init__(self) -> None:
        self.status = "completed"
        self.error: str | None = None
        self.detail: dict[str, Any] | None = None

    def skip(self) -> None:
        self.status = "skipped"


class RunTracker:
    """Start, step, and finish a run. A missing repository is a no-op."""

    def __init__(
        self,
        repository: RunRepository | None = None,
        *,
        log_path: str = "",
    ) -> None:
        self._repository = repository
        self._log_path = log_path

    async def start(
        self,
        task_type: str,
        input_json: dict[str, Any],
    ) -> uuid.UUID | None:
        if self._repository is None:
            return None
        safe = _plain_json(input_json)
        if not isinstance(safe, dict):
            safe = {}
        try:
            run = await self._repository.create(
                task_type=task_type,
                input_json=safe,
            )
        except Exception:
            logger.exception("Could not start run history")
            await self._rollback()
            return None
        self._write(
            run.id,
            step=None,
            event="run_started",
            status="running",
            error=None,
            level="info",
        )
        return run.id

    @asynccontextmanager
    async def step(
        self,
        run_id: uuid.UUID | None,
        name: str,
        *,
        attempt: int = 1,
    ) -> AsyncIterator[StepHandle]:
        handle = StepHandle()
        if self._repository is None or run_id is None:
            yield handle
            return
        row_id = await self._start_step(run_id, name, attempt)
        if row_id is None:
            yield handle
            return
        self._write(
            run_id,
            step=name,
            event="step_started",
            status="running",
            error=None,
            level="info",
        )
        try:
            yield handle
        except Exception as exc:
            await self._fail_open_step(run_id, row_id, name, exc, handle)
            raise
        except BaseException as exc:
            await self._fail_open_step(run_id, row_id, name, exc, handle)
            raise
        status = handle.status
        if status not in {"completed", "skipped", "failed"}:
            status = "completed"
        await self._finish_step(
            row_id,
            status=status,
            error=handle.error,
            detail=_safe_detail(handle.detail),
        )
        self._write(
            run_id,
            step=name,
            event="step_finished",
            status=status,
            error=handle.error,
            level="error" if status == "failed" else "info",
        )

    async def finish_current(
        self,
        run_id: uuid.UUID | None,
        *,
        output_json: dict[str, Any] | None = None,
    ) -> None:
        """Close the run from a finally block. Uses the active exception, if any."""
        exc = sys.exception()
        if exc is None:
            await self.finish(
                run_id,
                status="completed",
                output_json=output_json,
                error=None,
            )
            return
        await self.finish(
            run_id,
            status="failed",
            output_json=None,
            error=public_error(exc),
        )

    async def finish(
        self,
        run_id: uuid.UUID | None,
        *,
        status: str,
        output_json: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        if self._repository is None or run_id is None:
            return
        safe_output = _plain_json(output_json) if output_json is not None else None
        if safe_output is not None and not isinstance(safe_output, dict):
            safe_output = None
        safe_error = error[:_MAX_ERROR] if error else None
        try:
            await self._repository.finish(
                run_id,
                status=status,
                output_json=safe_output,
                error=safe_error,
            )
        except Exception:
            logger.exception("Could not finish run history")
            await self._rollback()
            return
        self._write(
            run_id,
            step=None,
            event="run_finished",
            status=status,
            error=safe_error,
            level="error" if status == "failed" else "info",
        )

    async def _fail_open_step(
        self,
        run_id: uuid.UUID,
        row_id: uuid.UUID,
        name: str,
        exc: BaseException,
        handle: StepHandle,
    ) -> None:
        message = public_error(exc)
        await self._finish_step(
            row_id,
            status="failed",
            error=message,
            detail=_safe_detail(handle.detail),
        )
        self._write(
            run_id,
            step=name,
            event="step_finished",
            status="failed",
            error=message,
            level="error",
        )

    async def _start_step(
        self,
        run_id: uuid.UUID,
        name: str,
        attempt: int,
    ) -> uuid.UUID | None:
        repository = self._repository
        if repository is None:
            return None
        try:
            row = await repository.start_step(run_id, name, attempt=attempt)
        except Exception:
            logger.exception("Could not start run step")
            await self._rollback()
            return None
        if row is None:
            return None
        return row.id

    async def _finish_step(
        self,
        step_id: uuid.UUID,
        *,
        status: str,
        error: str | None,
        detail: dict[str, Any] | None,
    ) -> None:
        repository = self._repository
        if repository is None:
            return
        try:
            await repository.finish_step(
                step_id,
                status=status,
                error=error,
                detail=detail,
            )
        except Exception:
            logger.exception("Could not finish run step")
            await self._rollback()

    async def _rollback(self) -> None:
        if self._repository is None:
            return
        try:
            await self._repository.rollback()
        except Exception:
            logger.exception("Could not roll back run history")

    def _write(
        self,
        run_id: uuid.UUID,
        *,
        step: str | None,
        event: str,
        status: str,
        error: str | None,
        level: str,
    ) -> None:
        append_run_log(
            self._log_path,
            {
                "level": level,
                "run_id": str(run_id),
                "step": step,
                "event": event,
                "status": status,
                "error": error,
            },
        )


def public_error(exc: BaseException | None) -> str | None:
    """Safe text for a run row. Unexpected errors stay generic."""
    if exc is None:
        return None
    if isinstance(exc, asyncio.CancelledError):
        return INTERRUPTED_MESSAGE
    if isinstance(exc, AppError):
        message = exc.message.strip() or "failed"
        return message[:_MAX_ERROR]
    return "failed"


def _plain_json(value: object, *, key: str | None = None) -> object:
    if key is not None and key.lower() in _SECRET_KEYS:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {
            str(item_key): _plain_json(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_plain_json(item) for item in value]
    if isinstance(value, str):
        return value if len(value) <= 500 else value[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return None


def _safe_detail(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    plain = _plain_json(value)
    if not isinstance(plain, dict) or not plain:
        return None
    return plain
