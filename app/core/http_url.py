"""Guards for outbound HTTP fetches (competitor pages)."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def is_public_http_url(url: str) -> bool:
    """True when the URL looks like public http(s), not a local/private host.

    Literal IPs are checked against private/loopback ranges. Hostnames are not
    DNS-resolved here (avoids flaky tests and extra latency); obvious local
    names are still rejected. Competitor URLs come from the search provider.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if not host:
        return False
    return _host_is_public(host)


def _host_is_public(host: str) -> bool:
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


def _is_blocked_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )

