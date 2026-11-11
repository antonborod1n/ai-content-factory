"""Unit tests for application logging setup."""

import logging

from app.config import Settings
from app.core.logging import configure_logging, resolve_log_level


def _settings(*, app_env: str = "local", log_level: str = "") -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://localhost/test",
        app_env=app_env,
        log_level=log_level,
    )


def test_explicit_log_level_wins_over_app_env() -> None:
    settings = _settings(app_env="test", log_level="debug")
    assert resolve_log_level(settings) == "DEBUG"


def test_test_env_defaults_to_warning() -> None:
    assert resolve_log_level(_settings(app_env="test")) == "WARNING"


def test_local_env_defaults_to_info() -> None:
    assert resolve_log_level(_settings(app_env="local")) == "INFO"


def test_unknown_log_level_falls_back_to_info() -> None:
    assert resolve_log_level(_settings(log_level="verbose")) == "INFO"


def test_configure_logging_sets_app_logger_level() -> None:
    app_logger = logging.getLogger("app")
    previous = app_logger.level
    try:
        configure_logging(_settings(log_level="DEBUG"))
        assert app_logger.getEffectiveLevel() == logging.DEBUG
    finally:
        configure_logging(_settings(log_level="WARNING"))
        app_logger.setLevel(previous)


def test_configure_logging_quiets_httpx_unless_debug() -> None:
    httpx_logger = logging.getLogger("httpx")
    previous = httpx_logger.level
    try:
        configure_logging(_settings(log_level="INFO"))
        assert httpx_logger.level == logging.WARNING

        configure_logging(_settings(log_level="DEBUG"))
        assert httpx_logger.level == logging.DEBUG
    finally:
        configure_logging(_settings(log_level="WARNING"))
        httpx_logger.setLevel(previous)


def test_configure_logging_does_not_drop_existing_handlers() -> None:
    root = logging.getLogger()
    before = list(root.handlers)
    configure_logging(_settings(log_level="INFO"))
    assert root.handlers == before
