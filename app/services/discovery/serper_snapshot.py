"""Serper.dev Google SERP snapshot (organic + PAA + related)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.exceptions import DiscoveryConfigurationError, DiscoveryUpstreamError
from app.schemas.discovery import SearchEngine, SerpOrganicHit, SerpSnapshot

logger = logging.getLogger(__name__)

_SERP_MAX_RESULTS = 100
_SERP_PAGE_SIZE = 10
_SERP_MAX_PAGES = 10


def parse_serper_payload(
    data: object,
    *,
    query: str,
    top_n: int,
    engine: SearchEngine = SearchEngine.GOOGLE,
) -> SerpSnapshot:
    """Map a Serper JSON body to SerpSnapshot. No HTTP."""
    payload = data if isinstance(data, dict) else {}
    needed = max(1, min(top_n, _SERP_MAX_RESULTS))
    organic_raw = payload.get("organic")
    organic: list[SerpOrganicHit] = []
    seen: set[str] = set()
    if isinstance(organic_raw, list):
        for raw in organic_raw:
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("link") or "").strip()
            title = str(raw.get("title") or "").strip()
            if not title or not url or url in seen:
                continue
            seen.add(url)
            organic.append(
                SerpOrganicHit(
                    title=title,
                    url=url,
                    snippet=str(raw.get("snippet") or "").strip(),
                    rank=len(organic) + 1,
                )
            )
            if len(organic) >= needed:
                break

    return SerpSnapshot(
        engine=engine,
        query=query,
        organic=organic,
        people_also_ask=_string_list(
            payload.get("peopleAlsoAsk"),
            keys=("question", "title"),
        ),
        related_searches=_string_list(
            payload.get("relatedSearches"),
            keys=("query", "text"),
        ),
    )


def _string_list(raw: object, *, keys: tuple[str, ...]) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = ""
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            for key in keys:
                text = str(item.get(key) or "").strip()
                if text:
                    break
        if not text:
            continue
        folded = text.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        values.append(text)
    return values


def merge_serper_pages(
    pages: list[object],
    *,
    query: str,
    top_n: int,
) -> SerpSnapshot:
    """Combine paginated Serper bodies: PAA/related from the first page."""
    if not pages:
        return SerpSnapshot(engine=SearchEngine.GOOGLE, query=query)
    first = parse_serper_payload(pages[0], query=query, top_n=top_n)
    organic = list(first.organic)
    seen = {hit.url for hit in organic}
    needed = max(1, min(top_n, _SERP_MAX_RESULTS))
    for page in pages[1:]:
        extra = parse_serper_payload(page, query=query, top_n=needed)
        for hit in extra.organic:
            if hit.url in seen:
                continue
            seen.add(hit.url)
            organic.append(
                SerpOrganicHit(
                    title=hit.title,
                    url=hit.url,
                    snippet=hit.snippet,
                    rank=len(organic) + 1,
                )
            )
            if len(organic) >= needed:
                break
        if len(organic) >= needed:
            break
    return first.model_copy(update={"organic": organic[:needed]})


class SerperSnapshotProvider:
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

    def is_configured(self, engine: SearchEngine) -> bool:
        return engine == SearchEngine.GOOGLE and bool(
            self._api_key and self._api_key.strip()
        )

    async def snapshot(
        self,
        query: str,
        *,
        engine: SearchEngine,
        top_n: int = 20,
    ) -> SerpSnapshot:
        cleaned = query.strip()
        if not cleaned:
            return SerpSnapshot(engine=SearchEngine.GOOGLE, query=query)
        if engine != SearchEngine.GOOGLE:
            raise DiscoveryConfigurationError("Serper only supports Google")
        if not self.is_configured(engine):
            raise DiscoveryConfigurationError("SERP API key is not configured")

        needed = max(1, min(top_n, _SERP_MAX_RESULTS))
        headers = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
        }
        client = self._client or httpx.AsyncClient(timeout=20.0)
        owns_client = self._client is None
        pages: list[Any] = []
        try:
            for page in range(1, _SERP_MAX_PAGES + 1):
                collected = 0
                if pages:
                    first = pages[0].get("organic") if isinstance(pages[0], dict) else []
                    collected = len(first) if isinstance(first, list) else 0
                    for extra in pages[1:]:
                        organic = extra.get("organic") if isinstance(extra, dict) else []
                        if isinstance(organic, list):
                            collected += len(organic)
                if collected >= needed:
                    break
                page_size = (
                    min(max(needed, _SERP_PAGE_SIZE), _SERP_MAX_RESULTS)
                    if page == 1
                    else _SERP_PAGE_SIZE
                )
                payload = await self._fetch_page(
                    client,
                    query=cleaned,
                    page=page,
                    num=page_size,
                    headers=headers,
                )
                organic = payload.get("organic") if isinstance(payload, dict) else None
                if not isinstance(organic, list) or not organic:
                    break
                pages.append(payload)
                if len(organic) < _SERP_PAGE_SIZE:
                    break
        finally:
            if owns_client:
                await client.aclose()

        snapshot = merge_serper_pages(pages, query=cleaned, top_n=needed)
        logger.info(
            "Serper snapshot organic=%s paa=%s related=%s query_length=%s",
            len(snapshot.organic),
            len(snapshot.people_also_ask),
            len(snapshot.related_searches),
            len(cleaned),
        )
        return snapshot

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        *,
        query: str,
        page: int,
        num: int,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        payload = {"q": query, "num": num, "page": page}
        try:
            response = await client.post(
                self._base_url, json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Serper HTTP error status=%s", exc.response.status_code)
            raise DiscoveryUpstreamError("Search provider failed") from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("Serper request failed")
            raise DiscoveryUpstreamError("Search provider failed") from exc
        if not isinstance(data, dict):
            return {}
        return data
