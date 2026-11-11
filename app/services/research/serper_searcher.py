"""Serper.dev Google SERP client."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings, get_settings
from app.core.competitor_filter import is_competitor_article_url
from app.core.exceptions import ResearchConfigurationError, ResearchUpstreamError
from app.schemas.research import SearchHit

logger = logging.getLogger(__name__)

# Serper accepts num 1–100. Paginate so filters can still fill RESEARCH_TOP_N.
_SERP_MAX_RESULTS = 100
_SERP_PAGE_SIZE = 10
_SERP_MAX_PAGES = 10


class SerperSearchProvider:
    """POST google.serper.dev/search. Does not call the API on init."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self._api_key = resolved.serp_api_key if api_key is None else api_key
        self._base_url = resolved.serp_base_url if base_url is None else base_url
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    async def search(self, query: str, *, top_n: int = 5) -> list[SearchHit]:
        cleaned = query.strip()
        if not cleaned:
            return []
        if not self.is_configured:
            raise ResearchConfigurationError("SERP API key is not configured")

        needed = max(1, min(top_n, _SERP_MAX_RESULTS))
        headers = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
        }
        client = self._client or httpx.AsyncClient(timeout=20.0)
        owns_client = self._client is None
        hits: list[SearchHit] = []
        seen: set[str] = set()
        try:
            for page in range(1, _SERP_MAX_PAGES + 1):
                if len(hits) >= needed:
                    break
                page_size = (
                    min(max(needed, _SERP_PAGE_SIZE), _SERP_MAX_RESULTS)
                    if page == 1
                    else _SERP_PAGE_SIZE
                )
                organic = await self._fetch_page(
                    client,
                    query=cleaned,
                    page=page,
                    num=page_size,
                    headers=headers,
                )
                if not organic:
                    break
                for raw in organic:
                    if not isinstance(raw, dict):
                        continue
                    url = str(raw.get("link") or "").strip()
                    title = str(raw.get("title") or "").strip()
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    if not title or not is_competitor_article_url(url):
                        continue
                    hits.append(
                        SearchHit(
                            title=title,
                            url=url,
                            snippet=str(raw.get("snippet") or "").strip(),
                            rank=len(hits) + 1,
                        )
                    )
                    if len(hits) >= needed:
                        break
                if len(organic) < _SERP_PAGE_SIZE:
                    break
        finally:
            if owns_client:
                await client.aclose()

        logger.info(
            "Serper returned %s organic hits for query length=%s",
            len(hits),
            len(cleaned),
        )
        return hits

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        *,
        query: str,
        page: int,
        num: int,
        headers: dict[str, str],
    ) -> list[object]:
        payload = {
            "q": query,
            "num": num,
            "page": page,
        }
        try:
            response = await client.post(
                self._base_url, json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Serper HTTP error status=%s", exc.response.status_code)
            raise ResearchUpstreamError("Search provider failed") from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("Serper request failed")
            raise ResearchUpstreamError("Search provider failed") from exc

        organic = data.get("organic") if isinstance(data, dict) else None
        if not isinstance(organic, list):
            return []
        return organic
