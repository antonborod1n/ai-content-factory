"""SerperSearchProvider with a mocked HTTP transport."""

import json

import httpx
import pytest

from app.core.exceptions import ResearchConfigurationError, ResearchUpstreamError
from app.services.research.serper_searcher import SerperSearchProvider


def _client_with(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler, base_url="https://google.serper.dev")


@pytest.mark.asyncio
async def test_serper_parses_organic_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-KEY"] == "test-key"
        body = json.loads(request.content)
        assert body["q"] == "жесткий матрас"
        return httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "title": "Статья 1",
                        "link": "https://example.com/one",
                        "snippet": "текст",
                    },
                    {
                        "title": "Local",
                        "link": "http://127.0.0.1/x",
                        "snippet": "skip",
                    },
                    {
                        "title": "Ролик",
                        "link": "https://www.youtube.com/watch?v=abc",
                        "snippet": "видео",
                    },
                    {
                        "title": "Карточка",
                        "link": "https://www.wildberries.ru/catalog/1",
                        "snippet": "купить",
                    },
                ]
            },
        )

    provider = SerperSearchProvider(
        api_key="test-key",
        base_url="https://google.serper.dev/search",
        client=_client_with(httpx.MockTransport(handler)),
    )
    hits = await provider.search("жесткий матрас", top_n=5)
    assert len(hits) == 1
    assert hits[0].url == "https://example.com/one"
    assert hits[0].title == "Статья 1"


@pytest.mark.asyncio
async def test_serper_paginates_until_top_n_article_urls() -> None:
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        page = int(body.get("page") or 1)
        pages.append(page)
        if page == 1:
            assert body["num"] == 12
            organic = [
                {
                    "title": "Ролик",
                    "link": "https://www.youtube.com/watch?v=abc",
                    "snippet": "видео",
                },
                *[
                    {
                        "title": f"Статья {index}",
                        "link": f"https://example.com/p1-{index}",
                        "snippet": "текст",
                    }
                    for index in range(1, 10)
                ],
            ]
        else:
            assert body["num"] == 10
            organic = [
                {
                    "title": f"Статья p2-{index}",
                    "link": f"https://example.com/p2-{index}",
                    "snippet": "текст",
                }
                for index in range(1, 11)
            ]
        return httpx.Response(200, json={"organic": organic})

    provider = SerperSearchProvider(
        api_key="test-key",
        base_url="https://google.serper.dev/search",
        client=_client_with(httpx.MockTransport(handler)),
    )
    hits = await provider.search("жесткий матрас", top_n=12)
    assert pages == [1, 2]
    assert len(hits) == 12
    assert hits[0].url == "https://example.com/p1-1"
    assert hits[-1].url == "https://example.com/p2-3"


@pytest.mark.asyncio
async def test_serper_requires_api_key() -> None:
    provider = SerperSearchProvider(api_key="")
    with pytest.raises(ResearchConfigurationError):
        await provider.search("q")


@pytest.mark.asyncio
async def test_serper_maps_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "nope"})

    provider = SerperSearchProvider(
        api_key="bad",
        client=_client_with(httpx.MockTransport(handler)),
    )
    with pytest.raises(ResearchUpstreamError):
        await provider.search("q")
