"""SerpAPI Yandex SERP snapshot (organic + related / PAA when present)."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings, get_settings
from app.core.exceptions import DiscoveryConfigurationError, DiscoveryUpstreamError
from app.schemas.discovery import SearchEngine, SerpOrganicHit, SerpSnapshot

logger = logging.getLogger(__name__)

_MAX_RESULTS = 50


def parse_serpapi_yandex_payload(
    data: object,
    *,
    query: str,
    top_n: int,
    engine: SearchEngine = SearchEngine.YANDEX,
) -> SerpSnapshot:
    """Map a SerpAPI Yandex JSON body to SerpSnapshot. No HTTP."""
    payload = data if isinstance(data, dict) else {}
    needed = max(1, min(top_n, _MAX_RESULTS))
    organic_raw = payload.get("organic_results")
    organic: list[SerpOrganicHit] = []
    seen: set[str] = set()
    if isinstance(organic_raw, list):
        for raw in organic_raw:
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("link") or raw.get("url") or "").strip()
            title = str(raw.get("title") or "").strip()
            if not title or not url or url in seen:
                continue
            seen.add(url)
            position = raw.get("position")
            rank = (
                int(position)
                if isinstance(position, int) and position >= 1
                else len(organic) + 1
            )
            organic.append(
                SerpOrganicHit(
                    title=title,
                    url=url,
                    snippet=str(raw.get("snippet") or "").strip(),
                    rank=rank,
                )
            )
            if len(organic) >= needed:
                break

    paa = _string_list(
        payload.get("people_also_ask") or payload.get("related_questions"),
        keys=("question", "title"),
    )
    related = _string_list(
        payload.get("related_searches"),
        keys=("query", "text"),
    )
    return SerpSnapshot(
        engine=engine,
        query=query,
        organic=organic,
        people_also_ask=paa,
        related_searches=related,
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


class YandexSerpApiProvider:
    """GET serpapi.com/search?engine=yandex. Does not call the API on init."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self._api_key = (
            resolved.yandex_serp_api_key if api_key is None else api_key
        )
        self._base_url = (
            resolved.yandex_serp_base_url if base_url is None else base_url
        )
        self._client = client

    def is_configured(self, engine: SearchEngine) -> bool:
        return engine == SearchEngine.YANDEX and bool(
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
            return SerpSnapshot(engine=SearchEngine.YANDEX, query=query)
        if engine != SearchEngine.YANDEX:
            raise DiscoveryConfigurationError("SerpAPI Yandex client only supports Yandex")
        if not self.is_configured(engine):
            raise DiscoveryConfigurationError("Yandex SERP API key is not configured")

        needed = max(1, min(top_n, _MAX_RESULTS))
        params = {
            "engine": "yandex",
            "text": cleaned,
            "num": needed,
            "api_key": self._api_key,
        }
        client = self._client or httpx.AsyncClient(timeout=20.0)
        owns_client = self._client is None
        try:
            response = await client.get(self._base_url, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Yandex SerpAPI HTTP error status=%s", exc.response.status_code
            )
            raise DiscoveryUpstreamError("Search provider failed") from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("Yandex SerpAPI request failed")
            raise DiscoveryUpstreamError("Search provider failed") from exc
        finally:
            if owns_client:
                await client.aclose()

        snapshot = parse_serpapi_yandex_payload(data, query=cleaned, top_n=needed)
        logger.info(
            "Yandex snapshot organic=%s paa=%s related=%s query_length=%s",
            len(snapshot.organic),
            len(snapshot.people_also_ask),
            len(snapshot.related_searches),
            len(cleaned),
        )
        return snapshot
