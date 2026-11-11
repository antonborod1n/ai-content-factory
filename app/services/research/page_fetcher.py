"""Fetch public HTML pages for structure parsing."""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.config import Settings, get_settings
from app.core.http_url import is_public_http_url

logger = logging.getLogger(__name__)


class PageFetcher(Protocol):
    """HTTP GET of competitor HTML. Implementations must not log bodies."""

    async def fetch(self, url: str) -> str | None:
        """Return HTML text, or None when the page cannot be used."""
        ...


class HttpPageFetcher:
    """httpx GET with size/timeout limits and a public-URL check."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float | None = None,
        max_bytes: int | None = None,
        user_agent: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self._timeout = (
            resolved.research_fetch_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        self._max_bytes = (
            resolved.research_max_page_bytes if max_bytes is None else max_bytes
        )
        self._user_agent = (
            resolved.research_user_agent if user_agent is None else user_agent
        )
        self._client = client

    async def fetch(self, url: str) -> str | None:
        if not is_public_http_url(url):
            logger.info("Skipping non-public research URL")
            return None

        headers = {"User-Agent": self._user_agent, "Accept": "text/html"}
        client = self._client or httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            max_redirects=3,
        )
        owns_client = self._client is None
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if "html" not in content_type and "text/plain" not in content_type:
                return None
            content = response.content[: self._max_bytes + 1]
            if len(content) > self._max_bytes:
                logger.info("Competitor page exceeded size limit")
                content = content[: self._max_bytes]
            return content.decode(response.encoding or "utf-8", errors="replace")
        except httpx.HTTPError:
            logger.info("Competitor page fetch failed")
            return None
        finally:
            if owns_client:
                await client.aclose()
