"""Process-wide logging for Docker and local uvicorn.

Uvicorn only configures its own loggers. Application loggers under ``app.*``
propagate to the root logger, which stays at WARNING unless we set it.
"""

from __future__ import annotations

import logging
import sys

from app.config import Settings, get_settings

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

ALLOWED_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "openai",
    "openai._base_client",
    "sqlalchemy.engine",
)


def resolve_log_level(settings: Settings | None = None) -> str:
    """Return an uppercase logging level.

    ``LOG_LEVEL`` wins when set. Otherwise ``APP_ENV=test`` is WARNING and
    everything else (local / production) is INFO.
    """
    resolved = settings or get_settings()
    explicit = (resolved.log_level or "").strip().upper()
    if explicit:
        if explicit in ALLOWED_LEVELS:
            return explicit
        return "INFO"

    env = (resolved.app_env or "").strip().lower()
    if env in {"test", "testing"}:
        return "WARNING"
    return "INFO"


def configure_logging(settings: Settings | None = None) -> str:
    """Point application logs at stdout so ``docker compose logs app`` shows them.

    Does not replace handlers already installed (pytest caplog, uvicorn).
    Never logs secrets: callers must not put keys or prompts in messages.
    """
    resolved = settings or get_settings()
    level_name = resolve_log_level(resolved)
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):
        level = logging.INFO
        level_name = "INFO"

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        handler.setLevel(level)
        root.addHandler(handler)

    logging.getLogger("app").setLevel(level)

    third_party_level = logging.DEBUG if level <= logging.DEBUG else logging.WARNING
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(third_party_level)

    return level_name
