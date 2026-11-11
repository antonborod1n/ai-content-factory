"""Deterministic SerpSnapshotProvider for tests."""

from __future__ import annotations

from app.schemas.discovery import (
    SearchEngine,
    SerpOrganicHit,
    SerpSnapshot,
)


def _default_snapshot(query: str, engine: SearchEngine) -> SerpSnapshot:
    host = "example.com" if engine == SearchEngine.GOOGLE else "example.org"
    return SerpSnapshot(
        engine=engine,
        query=query,
        organic=[
            SerpOrganicHit(
                title="Как выбрать жесткость матраса",
                url=f"https://{host}/mattress-firmness",
                snippet="Гид по жесткости",
                rank=1,
            ),
            SerpOrganicHit(
                title="Жесткий или мягкий матрас",
                url=f"https://{host}/hard-or-soft",
                snippet="Сравнение",
                rank=2,
            ),
            SerpOrganicHit(
                title="Матрас для сна на боку",
                url=f"https://{host}/side-sleeper",
                snippet="Поза сна",
                rank=3,
            ),
        ],
        people_also_ask=[
            "Какой матрас лучше для спины?",
            "Как понять жесткость матраса?",
        ],
        related_searches=[
            "жесткость матраса по весу",
            "кокосовый матрас",
        ],
    )


class MockSerpSnapshotProvider:
    """Records calls and returns canned snapshots. Never calls a provider."""

    def __init__(
        self,
        snapshots: dict[tuple[str, SearchEngine], SerpSnapshot] | None = None,
        *,
        configured: set[SearchEngine] | None = None,
    ) -> None:
        self.snapshots = snapshots or {}
        self.configured = (
            {SearchEngine.GOOGLE, SearchEngine.YANDEX}
            if configured is None
            else configured
        )
        self.calls: list[tuple[str, SearchEngine, int]] = []

    def is_configured(self, engine: SearchEngine) -> bool:
        return engine in self.configured

    async def snapshot(
        self,
        query: str,
        *,
        engine: SearchEngine,
        top_n: int = 20,
    ) -> SerpSnapshot:
        self.calls.append((query, engine, top_n))
        key = (query.strip(), engine)
        if key in self.snapshots:
            return self.snapshots[key]
        snapshot = _default_snapshot(query.strip(), engine)
        return snapshot.model_copy(update={"organic": snapshot.organic[:top_n]})
