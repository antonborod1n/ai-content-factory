"""HttpPageFetcher with a mocked transport."""

import socket
from unittest.mock import patch

import httpx
import pytest

from app.services.research.page_fetcher import HttpPageFetcher

_PUBLIC_DNS = [
    (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
]


@pytest.fixture(autouse=True)
def _public_example_dns() -> None:
    with patch("app.core.http_url.socket.getaddrinfo", return_value=_PUBLIC_DNS):
        yield


@pytest.mark.asyncio
async def test_fetch_returns_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "example.com" in str(request.url)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><h2>Hello</h2></html>",
        )

    fetcher = HttpPageFetcher(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        timeout_seconds=5,
        max_bytes=10_000,
        user_agent="test-agent",
    )
    html = await fetcher.fetch("https://example.com/page")
    assert html is not None
    assert "Hello" in html


@pytest.mark.asyncio
async def test_fetch_skips_private_urls() -> None:
    fetcher = HttpPageFetcher(
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200))
        )
    )
    assert await fetcher.fetch("http://127.0.0.1/secret") is None


@pytest.mark.asyncio
async def test_fetch_skips_redirect_to_private_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(
                302, headers={"location": "http://127.0.0.1/secret"}
            )
        return httpx.Response(200, text="should not read")

    fetcher = HttpPageFetcher(
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        )
    )
    assert await fetcher.fetch("https://example.com/start") is None


@pytest.mark.asyncio
async def test_fetch_skips_non_html() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"%PDF",
        )

    fetcher = HttpPageFetcher(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    assert await fetcher.fetch("https://example.com/file.pdf") is None
