"""Public-URL guard used before fetching competitor pages."""

import socket
from unittest.mock import patch

import pytest

from app.core.http_url import is_public_http_url, is_safe_fetch_url


def test_rejects_localhost_and_private_ips() -> None:
    assert is_public_http_url("https://localhost/x") is False
    assert is_public_http_url("http://127.0.0.1/secret") is False
    assert is_public_http_url("http://192.168.1.10/page") is False
    assert is_public_http_url("http://10.0.0.5/") is False


def test_rejects_non_http_schemes() -> None:
    assert is_public_http_url("file:///etc/passwd") is False
    assert is_public_http_url("ftp://example.com/a") is False
    assert is_public_http_url("not a url") is False


def test_accepts_public_literal_ip() -> None:
    assert is_public_http_url("https://8.8.8.8/lookup") is True


@pytest.mark.asyncio
async def test_safe_fetch_rejects_hostname_that_resolves_privately() -> None:
    loopback = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0)),
    ]
    with patch("app.core.http_url.socket.getaddrinfo", return_value=loopback):
        assert await is_safe_fetch_url("https://evil.example/page") is False


@pytest.mark.asyncio
async def test_safe_fetch_accepts_hostname_that_resolves_publicly() -> None:
    public = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
    ]
    with patch("app.core.http_url.socket.getaddrinfo", return_value=public):
        assert await is_safe_fetch_url("https://example.com/page") is True


@pytest.mark.asyncio
async def test_safe_fetch_rejects_private_literal_without_dns() -> None:
    assert await is_safe_fetch_url("http://10.0.0.5/") is False
