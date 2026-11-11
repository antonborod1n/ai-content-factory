"""Public-URL guard used before fetching competitor pages."""

from app.core.http_url import is_public_http_url


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
