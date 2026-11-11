"""Embedding client protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """Turns texts into dense vectors. Implementations live in the AI layer."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input string, in the same order."""
        ...
