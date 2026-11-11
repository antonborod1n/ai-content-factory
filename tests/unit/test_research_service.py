"""ResearchService orchestration with in-memory doubles."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.core.exceptions import ResearchError, ResearchUpstreamError
from app.db.models.research import ResearchRun, ResearchStatus
from app.schemas.research import ResearchRequest, SearchHit
from app.services.ai.mock_analyst import MockCompetitorAnalyst
from app.services.research.mock_page_fetcher import MockPageFetcher
from app.services.research.mock_searcher import MockSearchProvider
from app.services.research_service import ResearchService


class FakeResearchRepository:
    def __init__(self) -> None:
        self.runs: dict[Any, ResearchRun] = {}

    async def create(self, **fields: Any) -> ResearchRun:
        now = datetime.now(UTC)
        run = ResearchRun(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            **fields,
        )
        run.competitors = []
        self.runs[run.id] = run
        return run

    async def get_by_id(self, research_id: Any) -> ResearchRun | None:
        return self.runs.get(research_id)

    async def update(self, research_id: Any, **fields: Any) -> ResearchRun | None:
        run = self.runs.get(research_id)
        if run is None:
            return None
        for key, value in fields.items():
            setattr(run, key, value)
        return run

    async def add_competitors(
        self, research_id: Any, rows: list[dict[str, Any]]
    ) -> list[Any]:
        run = self.runs[research_id]
        from app.db.models.research import ResearchCompetitor

        created = []
        for row in rows:
            item = ResearchCompetitor(
                id=uuid4(),
                research_id=research_id,
                created_at=datetime.now(UTC),
                **row,
            )
            created.append(item)
        run.competitors = created
        return created


@pytest.mark.asyncio
async def test_analyze_builds_outline_from_mocked_serp() -> None:
    repo = FakeResearchRepository()
    service = ResearchService(
        repo,
        MockSearchProvider(),
        MockPageFetcher(),
        MockCompetitorAnalyst(),
        enabled=True,
        top_n=3,
        default_word_count=3000,
    )
    run = await service.analyze(ResearchRequest(topic="Жесткий или мягкий матрас"))
    assert run.status == ResearchStatus.COMPLETED
    assert len(run.outline) >= 2
    assert len(run.competitors) == 3
    assert any(row.fetch_status == "fetched" for row in run.competitors)


@pytest.mark.asyncio
async def test_analyze_requests_extra_serp_hits_to_fill_top_n() -> None:
    repo = FakeResearchRepository()
    searcher = MockSearchProvider()
    service = ResearchService(
        repo,
        searcher,
        MockPageFetcher(),
        MockCompetitorAnalyst(),
        enabled=True,
        top_n=10,
        search_n=40,
        default_word_count=3000,
    )
    run = await service.analyze(ResearchRequest(topic="Жесткий или мягкий матрас"))
    assert searcher.calls
    assert searcher.calls[0][1] == 40
    assert len(run.competitors) == 3


@pytest.mark.asyncio
async def test_analyze_fails_when_search_empty() -> None:
    repo = FakeResearchRepository()
    service = ResearchService(
        repo,
        MockSearchProvider(hits=[]),
        MockPageFetcher(),
        MockCompetitorAnalyst(),
        enabled=True,
        top_n=3,
        default_word_count=3000,
    )
    with pytest.raises(ResearchUpstreamError):
        await service.analyze(ResearchRequest(topic="Тема"))
    failed = next(iter(repo.runs.values()))
    assert failed.status == ResearchStatus.FAILED


class _BrokenSearchProvider(MockSearchProvider):
    async def search(self, *args: Any, **kwargs: Any) -> list[SearchHit]:
        raise ResearchError("Search provider misconfigured")


@pytest.mark.asyncio
async def test_analyze_marks_run_failed_on_research_error() -> None:
    repo = FakeResearchRepository()
    service = ResearchService(
        repo,
        _BrokenSearchProvider(hits=[]),
        MockPageFetcher(),
        MockCompetitorAnalyst(),
        enabled=True,
        top_n=3,
        default_word_count=3000,
    )
    with pytest.raises(ResearchError):
        await service.analyze(ResearchRequest(topic="Тема"))
    failed = next(iter(repo.runs.values()))
    assert failed.status == ResearchStatus.FAILED
    assert failed.error_message == "Search provider misconfigured"


@pytest.mark.asyncio
async def test_attach_replaces_outline_on_write_input() -> None:
    repo = FakeResearchRepository()
    service = ResearchService(
        repo,
        MockSearchProvider(),
        MockPageFetcher(),
        MockCompetitorAnalyst(),
        enabled=True,
        top_n=3,
        default_word_count=3000,
    )
    from app.schemas.ai import ArticleWriteInput

    request = ArticleWriteInput(
        topic="Жесткий или мягкий матрас",
        outline=["Свой план"],
        use_competitor_research=True,
    )
    updated = await service.attach_to_write_input(request)
    assert updated.outline != ["Свой план"]
    assert updated.competitor_context
    assert updated.research_id is not None
    assert "Конкурент" in updated.competitor_context
    assert [item.url for item in updated.competitor_sources] == [
        "https://example.com/firm-mattress",
        "https://example.com/soft-mattress",
        "https://example.com/firmness-guide",
    ]
    assert updated.section_image_placeholders
    assert len(updated.section_image_placeholders) == len(updated.outline)
    assert updated.image_placeholders == sum(updated.section_image_placeholders)
    assert any(page for page in updated.competitor_image_sections)
    assert updated.word_count is not None
    assert updated.word_count >= 400
    assert updated.article_goal
    assert updated.include_lists is True
    assert updated.faq_count >= 0
    assert updated.infographic_placeholders >= 0


def _service(
    *,
    hits: list[SearchHit] | None = None,
    fetcher: MockPageFetcher | None = None,
) -> tuple[ResearchService, FakeResearchRepository, MockPageFetcher]:
    repo = FakeResearchRepository()
    page_fetcher = fetcher or MockPageFetcher()
    service = ResearchService(
        repo,
        MockSearchProvider(hits=hits),
        page_fetcher,
        MockCompetitorAnalyst(),
        enabled=True,
        top_n=3,
        search_n=10,
        min_article_chars=300,
        default_word_count=3000,
    )
    return service, repo, page_fetcher


@pytest.mark.asyncio
async def test_analyze_skips_video_shops_short_and_failed_pages() -> None:
    fetcher = MockPageFetcher()
    fetcher.pages["https://example.com/short"] = "<h1>Тема</h1><p>Мало текста.</p>"
    service, _repo, used_fetcher = _service(
        hits=[
            SearchHit(
                title="Ролик",
                url="https://www.youtube.com/watch?v=abc",
                rank=1,
            ),
            SearchHit(
                title="Карточка",
                url="https://www.wildberries.ru/catalog/123",
                rank=2,
            ),
            SearchHit(
                title="Витрина",
                url="https://hoff.ru/catalog/matrasy/",
                rank=3,
            ),
            SearchHit(
                title="Коротко",
                url="https://example.com/short",
                rank=4,
            ),
            SearchHit(
                title="Нет страницы",
                url="https://example.com/missing",
                rank=5,
            ),
            SearchHit(
                title="Жесткий матрас: плюсы и минусы",
                url="https://example.com/firm-mattress",
                rank=6,
            ),
        ],
        fetcher=fetcher,
    )
    run = await service.analyze(ResearchRequest(topic="Жесткий или мягкий матрас"))
    assert run.status == ResearchStatus.COMPLETED
    assert [row.url for row in run.competitors] == [
        "https://example.com/firm-mattress"
    ]
    assert run.competitors[0].rank == 1
    assert run.competitors[0].fetch_status == "fetched"
    assert "https://www.youtube.com/watch?v=abc" not in used_fetcher.calls
    assert "https://www.wildberries.ru/catalog/123" not in used_fetcher.calls
    assert "https://hoff.ru/catalog/matrasy/" not in used_fetcher.calls
    assert "https://example.com/missing" in used_fetcher.calls


@pytest.mark.asyncio
async def test_analyze_fails_when_serp_has_no_articles() -> None:
    service, repo, _fetcher = _service(
        hits=[
            SearchHit(
                title="Ролик",
                url="https://www.youtube.com/watch?v=abc",
                rank=1,
            )
        ]
    )
    with pytest.raises(ResearchUpstreamError, match="No suitable competitor articles"):
        await service.analyze(ResearchRequest(topic="Тема"))
    failed = next(iter(repo.runs.values()))
    assert failed.status == ResearchStatus.FAILED
