"""Unit tests for MockEmbedder (no provider calls)."""

import pytest

from app.core.embedding_const import EMBEDDING_DIMENSIONS
from app.services.ai.mock_embedder import MockEmbedder


@pytest.mark.asyncio
async def test_same_text_yields_same_vector() -> None:
    embedder = MockEmbedder()
    first, second = await embedder.embed(["промышленный насос", "промышленный насос"])
    assert first == second
    assert len(first) == EMBEDDING_DIMENSIONS


@pytest.mark.asyncio
async def test_overlapping_tokens_are_closer_than_unrelated_text() -> None:
    embedder = MockEmbedder()
    query, related, other = await embedder.embed(
        [
            "промышленный насос напор",
            "как выбрать промышленный насос по напору",
            "рецепт борща со сметаной",
        ]
    )

    def _dot(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right, strict=True))

    assert _dot(query, related) > _dot(query, other)
