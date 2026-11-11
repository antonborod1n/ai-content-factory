"""Serper snapshot mapper and HTTP client with a mocked transport."""

import json

import httpx
import pytest

from app.core.exceptions import DiscoveryConfigurationError, DiscoveryUpstreamError
from app.schemas.discovery import SearchEngine
from app.services.discovery.serper_snapshot import (
    SerperSnapshotProvider,
    parse_serper_payload,
)


def test_parse_serper_payload_maps_organic_paa_related() -> None:
    snapshot = parse_serper_payload(
        {
            "organic": [
                {
                    "title": "Статья 1",
                    "link": "https://example.com/one",
                    "snippet": "текст",
                },
                {"title": "", "link": "https://example.com/skip"},
                {
                    "title": "Витрина",
                    "link": "https://www.wildberries.ru/catalog/1",
                    "snippet": "купить",
                },
            ],
            "peopleAlsoAsk": [
                {"question": "Какой матрас выбрать?"},
                {"question": "Какой матрас выбрать?"},
            ],
            "relatedSearches": [{"query": "жесткость матраса"}, "кокос"],
        },
        query="матрас",
        top_n=10,
    )
    assert snapshot.engine == SearchEngine.GOOGLE
    assert [hit.title for hit in snapshot.organic] == ["Статья 1", "Витрина"]
    assert snapshot.people_also_ask == ["Какой матрас выбрать?"]
    assert snapshot.related_searches == ["жесткость матраса", "кокос"]


def _client_with(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler, base_url="https://google.serper.dev")


@pytest.mark.asyncio
async def test_serper_snapshot_paginates_organic() -> None:
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        page = int(body.get("page") or 1)
        pages.append(page)
        organic = [
            {
                "title": f"Статья {page}-{index}",
                "link": f"https://example.com/p{page}-{index}",
                "snippet": "текст",
            }
            for index in range(1, 11)
        ]
        extra = (
            {
                "peopleAlsoAsk": [{"question": "Вопрос?"}],
                "relatedSearches": [{"query": "related"}],
            }
            if page == 1
            else {}
        )
        return httpx.Response(200, json={"organic": organic, **extra})

    provider = SerperSnapshotProvider(
        api_key="test-key",
        base_url="https://google.serper.dev/search",
        client=_client_with(httpx.MockTransport(handler)),
    )
    snapshot = await provider.snapshot("матрас", engine=SearchEngine.GOOGLE, top_n=12)
    assert pages == [1, 2]
    assert len(snapshot.organic) == 12
    assert snapshot.people_also_ask == ["Вопрос?"]
    assert snapshot.related_searches == ["related"]


@pytest.mark.asyncio
async def test_serper_snapshot_requires_google_key() -> None:
    provider = SerperSnapshotProvider(api_key="")
    with pytest.raises(DiscoveryConfigurationError):
        await provider.snapshot("q", engine=SearchEngine.GOOGLE)


@pytest.mark.asyncio
async def test_serper_snapshot_maps_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "nope"})

    provider = SerperSnapshotProvider(
        api_key="bad",
        client=_client_with(httpx.MockTransport(handler)),
    )
    with pytest.raises(DiscoveryUpstreamError):
        await provider.snapshot("q", engine=SearchEngine.GOOGLE)
