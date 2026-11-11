"""Deterministic SearchProvider for tests."""

from __future__ import annotations

from app.schemas.research import SearchHit

_DEFAULT_HITS = (
    SearchHit(
        title="Жесткий матрас: плюсы и минусы",
        url="https://example.com/firm-mattress",
        snippet="Обзор жестких матрасов и веса покупателя.",
        rank=1,
    ),
    SearchHit(
        title="Мягкий матрас для сна на боку",
        url="https://example.com/soft-mattress",
        snippet="Когда выбирать мягкую модель и как не ошибиться.",
        rank=2,
    ),
    SearchHit(
        title="Как выбрать жесткость матраса",
        url="https://example.com/firmness-guide",
        snippet="Таблица по позе сна и FAQ.",
        rank=3,
    ),
)


class MockSearchProvider:
    """Returns fixed example.com hits. Never talks to a SERP API."""

    def __init__(self, hits: list[SearchHit] | None = None) -> None:
        self.hits = list(hits) if hits is not None else list(_DEFAULT_HITS)
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, top_n: int = 5) -> list[SearchHit]:
        self.calls.append((query, top_n))
        return [hit.model_copy() for hit in self.hits[:top_n]]
