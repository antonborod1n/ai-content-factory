"""DiscoveryService orchestration with in-memory doubles."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.core.exceptions import (
    DiscoveryConfigurationError,
    DiscoveryUpstreamError,
)
from app.db.models.discovery import ContentPlan, ContentPlanStatus, ContentPlanTopic
from app.schemas.discovery import DiscoveryRequest, SearchEngine
from app.services.ai.mock_topic_planner import MockTopicPlanner
from app.services.discovery.mock_snapshotter import MockSerpSnapshotProvider
from app.services.discovery_service import DiscoveryService, flatten_candidates


class FakeDiscoveryRepository:
    def __init__(self) -> None:
        self.plans: dict[Any, ContentPlan] = {}

    async def create(self, **fields: Any) -> ContentPlan:
        now = datetime.now(UTC)
        plan = ContentPlan(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            **fields,
        )
        plan.topics = []
        self.plans[plan.id] = plan
        return plan

    async def get_by_id(self, plan_id: Any) -> ContentPlan | None:
        return self.plans.get(plan_id)

    async def update(self, plan_id: Any, **fields: Any) -> ContentPlan | None:
        plan = self.plans.get(plan_id)
        if plan is None:
            return None
        for key, value in fields.items():
            setattr(plan, key, value)
        return plan

    async def add_topics(
        self, plan_id: Any, rows: list[dict[str, Any]]
    ) -> list[ContentPlanTopic]:
        plan = self.plans[plan_id]
        created = []
        for row in rows:
            item = ContentPlanTopic(
                id=uuid4(),
                plan_id=plan_id,
                created_at=datetime.now(UTC),
                **row,
            )
            created.append(item)
        plan.topics = created
        return created


def _service(
    repo: FakeDiscoveryRepository,
    snapshotter: MockSerpSnapshotProvider | None = None,
    planner: MockTopicPlanner | None = None,
    *,
    enabled: bool = True,
    **kwargs: Any,
) -> DiscoveryService:
    return DiscoveryService(
        repo,
        snapshotter or MockSerpSnapshotProvider(),
        planner or MockTopicPlanner(),
        enabled=enabled,
        max_topics=5,
        search_n=10,
        topics_file_path="",
        default_word_count=3000,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_discover_builds_briefs_from_snapshots() -> None:
    repo = FakeDiscoveryRepository()
    snapshotter = MockSerpSnapshotProvider()
    service = _service(repo, snapshotter)
    plan = await service.discover(
        DiscoveryRequest(seeds=["жесткость матраса"], niche="матрасы")
    )
    assert plan.status == ContentPlanStatus.COMPLETED
    assert plan.topics
    assert plan.engines_used == ["google", "yandex"]
    assert snapshotter.calls
    assert {engine for _, engine, _ in snapshotter.calls} == {
        SearchEngine.GOOGLE,
        SearchEngine.YANDEX,
    }
    assert plan.topics[0].brief["topic"]
    assert plan.topics[0].brief["language"] == "ru"
    assert plan.topics[0].brief["word_count"] == 3000
    assert "use_knowledge_base" in plan.topics[0].brief


@pytest.mark.asyncio
async def test_discover_omits_analysis_fields_when_research_is_on() -> None:
    repo = FakeDiscoveryRepository()
    service = _service(repo)
    plan = await service.discover(
        DiscoveryRequest(
            seeds=["жесткость матраса"],
            use_competitor_research=True,
            word_count=2500,
        )
    )
    brief = plan.topics[0].brief
    assert brief["use_competitor_research"] is True
    assert brief["use_knowledge_base"] is True
    assert "word_count" not in brief
    assert "outline" not in brief
    assert "image_placeholders" not in brief


@pytest.mark.asyncio
async def test_discover_skips_yandex_when_not_configured() -> None:
    repo = FakeDiscoveryRepository()
    snapshotter = MockSerpSnapshotProvider(configured={SearchEngine.GOOGLE})
    service = _service(repo, snapshotter)
    plan = await service.discover(DiscoveryRequest(seeds=["матрас"]))
    assert plan.engines_used == ["google"]
    assert all(engine == SearchEngine.GOOGLE for _, engine, _ in snapshotter.calls)


@pytest.mark.asyncio
async def test_discover_requires_google_key() -> None:
    repo = FakeDiscoveryRepository()
    snapshotter = MockSerpSnapshotProvider(configured=set())
    service = _service(repo, snapshotter)
    with pytest.raises(DiscoveryConfigurationError):
        await service.discover(DiscoveryRequest(seeds=["матрас"]))


@pytest.mark.asyncio
async def test_discover_disabled() -> None:
    repo = FakeDiscoveryRepository()
    service = _service(repo, enabled=False)
    with pytest.raises(DiscoveryConfigurationError, match="disabled"):
        await service.discover(DiscoveryRequest(seeds=["матрас"]))


@pytest.mark.asyncio
async def test_export_appends_unique_topics(tmp_path) -> None:
    repo = FakeDiscoveryRepository()
    service = _service(repo)
    plan = await service.discover(DiscoveryRequest(seeds=["матрас"]))
    dest = tmp_path / "topics.json"
    dest.write_text(
        '[{"topic": "Как выбрать жесткость матраса"}]\n',
        encoding="utf-8",
    )
    result = await service.export(plan.id, path=str(dest))
    assert result.added + result.skipped == len(plan.topics)
    assert result.skipped >= 1


@pytest.mark.asyncio
async def test_planner_failure_marks_failed() -> None:
    repo = FakeDiscoveryRepository()
    planner = MockTopicPlanner(fail_with=DiscoveryUpstreamError("planner"))
    service = _service(repo, planner=planner)
    # MockTopicPlanner wraps non-AIError; pass AIError via fail_with
    from app.core.exceptions import AIProviderError

    planner.fail_with = AIProviderError("planner")
    with pytest.raises(DiscoveryUpstreamError):
        await service.discover(DiscoveryRequest(seeds=["матрас"]))
    plan = next(iter(repo.plans.values()))
    assert plan.status == ContentPlanStatus.FAILED


def test_flatten_candidates() -> None:
    from app.schemas.discovery import SerpOrganicHit, SerpSnapshot

    snapshots = [
        SerpSnapshot(
            engine=SearchEngine.GOOGLE,
            query="матрас",
            organic=[
                SerpOrganicHit(
                    title="Тема",
                    url="https://example.com/a",
                    rank=1,
                )
            ],
            people_also_ask=["Вопрос?"],
            related_searches=["related"],
        )
    ]
    items = flatten_candidates(snapshots)
    assert [item.kind.value for item in items] == ["organic", "paa", "related"]
