"""Deterministic embedder for tests (no provider calls)."""

from __future__ import annotations

import hashlib
import math
import re

from app.core.embedding_const import EMBEDDING_DIMENSIONS

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class MockEmbedder:
    """Bag-of-words hash embeddings so overlapping text ranks closer.

    Same string always yields the same vector. Tests can ingest a document and
    retrieve it with a query that shares distinctive tokens.
    """

    def __init__(self, *, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self._dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        dim = self._dimensions
        vec = [0.0] * dim
        tokens = _TOKEN_RE.findall(text.lower()) or [""]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % dim
            vec[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vec)) or 1.0
        return [value / norm for value in vec]
