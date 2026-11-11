"""Yandex SerpAPI mapper and HTTP client with a mocked transport."""

import httpx
import pytest

from app.core.exceptions import DiscoveryConfigurationError, DiscoveryUpstreamError
from app.schemas.discovery import SearchEngine
from app.services.discovery.yandex_serpapi import (
    YandexSerpApiProvider,
    parse_serpapi_yandex_payload,
)


def test_parse_serpapi_yandex_payload() -> None:
    snapshot = parse_serpapi_yandex_payload(
        {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Тема Яндекса",
                    "link": "https://example.org/one",
                    "snippet": "сниппет",
                },
                {"title": "Без ссылки"},
            ],
            "related_searches": [{"query": "похожий запрос"}],
            "related_questions": [{"question": "Люди спрашивают?"}],
        },
        query="матрас",
        top_n=10,
    )
    assert snapshot.engine == SearchEngine.YANDEX
    assert snapshot.organic[0].title == "Тема Яндекса"
    assert snapshot.related_searches == ["похожий запрос"]
    assert snapshot.people_also_ask == ["Люди спрашивают?"]


def _client_with(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler, base_url="https://serpapi.com")


@pytest.mark.asyncio
async def test_yandex_snapshot_sends_engine_and_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["engine"] == "yandex"
        assert request.url.params["text"] == "жесткость матраса"
        assert request.url.params["api_key"] == "yandex-key"
        return httpx.Response(
            200,
            json={
                "organic_results": [
                    {
                        "title": "Статья",
                        "link": "https://example.org/a",
                        "snippet": "текст",
                    }
                ]
            },
        )

    provider = YandexSerpApiProvider(
        api_key="yandex-key",
        base_url="https://serpapi.com/search",
        client=_client_with(httpx.MockTransport(handler)),
    )
    snapshot = await provider.snapshot(
        "жесткость матраса", engine=SearchEngine.YANDEX, top_n=5
    )
    assert snapshot.organic[0].url == "https://example.org/a"


@pytest.mark.asyncio
async def test_yandex_snapshot_requires_key() -> None:
    provider = YandexSerpApiProvider(api_key="")
    with pytest.raises(DiscoveryConfigurationError):
        await provider.snapshot("q", engine=SearchEngine.YANDEX)


@pytest.mark.asyncio
async def test_yandex_snapshot_maps_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "nope"})

    provider = YandexSerpApiProvider(
        api_key="bad",
        client=_client_with(httpx.MockTransport(handler)),
    )
    with pytest.raises(DiscoveryUpstreamError):
        await provider.snapshot("q", engine=SearchEngine.YANDEX)
