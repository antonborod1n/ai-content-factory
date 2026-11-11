"""One constructor for chat, embedding, and image clients."""

from __future__ import annotations

from openai import AsyncOpenAI

# A single extra attempt covers a dropped connection. Further retries would
# keep the operator spinner up long after the call has already failed.
_MAX_RETRIES = 1


def build_async_openai(
    *,
    api_key: str,
    base_url: str | None,
    timeout: float,
) -> AsyncOpenAI:
    """Build a client that stops waiting after `timeout` seconds."""
    if base_url:
        return AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=_MAX_RETRIES,
        )
    return AsyncOpenAI(
        api_key=api_key,
        timeout=timeout,
        max_retries=_MAX_RETRIES,
    )
