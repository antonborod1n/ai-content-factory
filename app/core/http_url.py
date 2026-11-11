"""Guards for outbound HTTP fetches (competitor pages)."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


def is_public_http_url(url: str) -> bool:
    """True when the URL looks like public http(s), not an obvious local host.

    Literal IPs are checked against private/loopback ranges. Hostnames still
    need ``is_safe_fetch_url`` (DNS resolve) before an actual GET.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if not host:
        return False
    return _host_looks_public(host)


async def is_safe_fetch_url(url: str) -> bool:
    """Like ``is_public_http_url``, plus DNS resolve and block private answers."""
    if not is_public_http_url(url):
        return False
    host = urlparse(url.strip()).hostname
    if not host:
        return False
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        return await _resolved_addresses_are_public(host)
    return not _is_blocked_ip(literal)


def _host_looks_public(host: str) -> bool:
    lowered = host.lower().rstrip(".")
    if lowered in {"localhost", "metadata.google.internal"}:
        return False
    if lowered.endswith(".localhost") or lowered.endswith(".local"):
        return False
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not _is_blocked_ip(literal)


async def _resolved_addresses_are_public(host: str) -> bool:
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, host, None, type=socket.SOCK_STREAM
        )
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            return False
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if _is_blocked_ip(address):
            return False
    return True


def _is_blocked_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
