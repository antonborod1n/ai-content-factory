"""Prepare the dedicated test database.

Tests truncate tables, so they must never run against the application
database. This module derives a separate database name, creates it if needed
and brings it to the latest migration.

Run directly with `python -m tests.db_setup`; `conftest.py` does that once per
session in a subprocess to keep Alembic away from the pytest event loop.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from urllib.parse import urlparse, urlunparse

TEST_DATABASE_SUFFIX = "_test"


def derive_test_database_url(application_url: str) -> str:
    """Return the same server and credentials with a `_test` database name.

    An explicit `TEST_DATABASE_URL` always wins.
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit

    parsed = urlparse(application_url)
    name = parsed.path.lstrip("/")
    if name.endswith(TEST_DATABASE_SUFFIX):
        return application_url
    return urlunparse(parsed._replace(path=f"/{name}{TEST_DATABASE_SUFFIX}"))


def _split_database_name(url: str) -> tuple[str, str]:
    """Split a URL into (server URL pointing at `postgres`, database name)."""
    parsed = urlparse(url)
    name = parsed.path.lstrip("/")
    server_url = urlunparse(parsed._replace(path="/postgres"))
    return server_url, name


async def _create_database_if_missing(url: str) -> None:
    import asyncpg

    server_url, name = _split_database_name(url)
    dsn = server_url.replace("postgresql+asyncpg://", "postgresql://")

    connection = await asyncpg.connect(dsn)
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", name
        )
        if not exists:
            # asyncpg forbids parameters in DDL; the name is derived, not input.
            await connection.execute(f'CREATE DATABASE "{name}"')
    finally:
        await connection.close()


def _run_migrations(url: str) -> None:
    environment = {**os.environ, "DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=environment,
        capture_output=True,
    )


def prepare_test_database(url: str) -> None:
    asyncio.run(_create_database_if_missing(url))
    _run_migrations(url)


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL must be set to prepare the test database")
    prepare_test_database(url)


if __name__ == "__main__":
    main()
