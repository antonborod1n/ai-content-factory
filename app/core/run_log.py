"""Append-only JSONL journal for task runs. No article bodies or secrets."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_FIELDS = ("timestamp", "level", "run_id", "step", "event", "status", "error")


def append_run_log(path: str | Path, record: dict[str, object]) -> None:
    """Write one JSON object. Failures are logged and swallowed."""
    text = str(path).strip()
    if not text:
        return
    line = {key: record.get(key) for key in _LOG_FIELDS}
    if line["timestamp"] is None:
        line["timestamp"] = datetime.now(UTC).isoformat()
    try:
        target = Path(text)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        logger.warning("Could not append run log")
