"""CompetitorTopicsService with an in-memory repository double."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.core.exceptions import (
    AIError,
    CompetitorTopicsConfigurationError,
    CompetitorTopicsNotFoundError,
    CompetitorTopicsParseError,
    CompetitorTopicsUpstreamError,
)
from app.db.models.discovery import ContentPlan, ContentPlanSource, ContentPlanStatus, ContentPlanTopic
from app.schemas.competitor_topics import (
    CompetitorTopicsImportRequest,
    CompetitorTopicsSourcesRequest,
    ContentGapOutput,
)
from app.services.ai.mock_content_gap import MockContentGapAnalyst
from app.services.competitor_topics_service import CompetitorTopicsService


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

    async def list(
        self, *, limit: int = 50, offset: int = 0, source: str | None = None
    ) -> list[ContentPlan]:
        items = list(self.plans.values())
        if source is not None:
            items = [item for item in items if item.source == source]
        return items[offset : offset + limit]

    async def count(self, *, source: str | None = None) -> int:
        items = list(self.plans.values())
        if source is not None:
            items = [item for item in items if item.source == source]
        return len(items)


SAMPLE = {
    "domain": "goodnight.by",
    "niche": "товары для сна",
    "audience": "Покупатели матрасов",
    "geo": "Беларусь",
    "siteType": "интернет-магазин",
    "topics": [
        {
            "title": "Какой матрас выбрать в Беларуси",
            "category": "Выбор матраса",
            "priority": "High",
            "competitors": ["Promatras"],
            "isGap": False,
            "uniqueAngle": "Хаб с таблицей.",
            "intent": "informational / howto",
            "commercialLink": "Категория матрасов",
        },
        {
            "title": "Что такое шаум в матрасе",
            "category": "Наполнители",
            "priority": "High",
            "competitors": ["gap"],
            "isGap": True,
            "uniqueAngle": "Ключ клиента.",
            "intent": "informational",
            "commercialLink": "Беспружинные",
        },
    ],
}


def _service(
    repo: FakeDiscoveryRepository,
    *,
    enabled: bool = True,
    topics_file_path: str = "",
    analyst: MockContentGapAnalyst | None = None,
) -> CompetitorTopicsService:
    return CompetitorTopicsService(
        repo,
        analyst if analyst is not None else MockContentGapAnalyst(),
        enabled=enabled,
        topics_file_path=topics_file_path,
    )


@pytest.mark.asyncio
async def test_import_plan_persists_briefs_and_metadata() -> None:
    repo = FakeDiscoveryRepository()
    service = _service(repo)
    plan = await service.import_plan(
        CompetitorTopicsImportRequest.model_validate(SAMPLE)
    )
    assert plan.status == ContentPlanStatus.COMPLETED
    assert plan.source == ContentPlanSource.COMPETITOR_GAP.value
    assert plan.context["domain"] == "goodnight.by"
    assert plan.context["geo"] == "Беларусь"
    assert len(plan.topics) == 2
    first = plan.topics[0]
    assert first.brief["topic"] == "Какой матрас выбрать в Беларуси"
    assert first.brief["search_intent"] == "informational_howto"
    assert "outline" not in first.brief
    assert first.source_competitors == ["Promatras"]
    assert first.is_gap is False
    assert first.priority == "High"
    assert plan.topics[1].is_gap is True
    assert plan.topics[1].source_competitors == []


@pytest.mark.asyncio
async def test_import_disabled() -> None:
    service = _service(FakeDiscoveryRepository(), enabled=False)
    with pytest.raises(CompetitorTopicsConfigurationError):
        await service.import_plan(CompetitorTopicsImportRequest.model_validate(SAMPLE))


@pytest.mark.asyncio
async def test_get_ignores_serp_plans() -> None:
    repo = FakeDiscoveryRepository()
    service = _service(repo)
    serp = await repo.create(
        niche="матрасы",
        source=ContentPlanSource.SERP.value,
        status=ContentPlanStatus.COMPLETED,
    )
    with pytest.raises(CompetitorTopicsNotFoundError):
        await service.get(serp.id)


@pytest.mark.asyncio
async def test_export_writes_topics_file(tmp_path) -> None:
    repo = FakeDiscoveryRepository()
    dest = tmp_path / "topics.json"
    service = _service(repo, topics_file_path=str(dest))
    plan = await service.import_plan(
        CompetitorTopicsImportRequest.model_validate(SAMPLE)
    )
    result = await service.export(plan.id)
    assert result.added == 2
    assert dest.is_file()


@pytest.mark.asyncio
async def test_ingest_csv_uses_analyst() -> None:
    repo = FakeDiscoveryRepository()
    analyst = MockContentGapAnalyst()
    service = _service(repo, analyst=analyst)
    plan = await service.ingest_sources(
        [("promatras.csv", "keyword\nкакой матрас выбрать\n".encode("utf-8"))],
        CompetitorTopicsSourcesRequest(
            domain="goodnight.by",
            niche="товары для сна",
            audience="Покупатели матрасов",
            geo="Беларусь",
        ),
    )
    assert plan.status == ContentPlanStatus.COMPLETED
    assert plan.context["source_files"] == ["promatras.csv"]
    assert plan.topics[0].brief["topic"] == "какой матрас выбрать"
    assert analyst.calls
    assert analyst.calls[0].hits[0].text == "какой матрас выбрать"


@pytest.mark.asyncio
async def test_ingest_ready_json_skips_analyst() -> None:
    repo = FakeDiscoveryRepository()
    analyst = MockContentGapAnalyst()
    service = _service(repo, analyst=analyst)
    payload = json.dumps(SAMPLE, ensure_ascii=False).encode("utf-8")
    plan = await service.ingest_sources(
        [("plan.json", payload)],
        CompetitorTopicsSourcesRequest(domain="goodnight.by"),
    )
    assert len(plan.topics) == 2
    assert analyst.calls == []


@pytest.mark.asyncio
async def test_ingest_falls_back_when_analyst_returns_empty() -> None:
    repo = FakeDiscoveryRepository()
    service = _service(repo, analyst=MockContentGapAnalyst(output=ContentGapOutput()))
    plan = await service.ingest_sources(
        [("keys.txt", "жесткость матраса\n".encode("utf-8"))],
        CompetitorTopicsSourcesRequest(domain="goodnight.by"),
    )
    assert plan.topics[0].brief["topic"] == "жесткость матраса"


@pytest.mark.asyncio
async def test_ingest_maps_analyst_failure() -> None:
    repo = FakeDiscoveryRepository()
    service = _service(repo, analyst=MockContentGapAnalyst(fail_with=AIError("boom")))
    with pytest.raises(CompetitorTopicsUpstreamError):
        await service.ingest_sources(
            [("keys.txt", "какой матрас выбрать\n".encode("utf-8"))],
            CompetitorTopicsSourcesRequest(),
        )
    failed = next(iter(repo.plans.values()))
    assert failed.status == ContentPlanStatus.FAILED


@pytest.mark.asyncio
async def test_ingest_no_topics_raises_before_persist() -> None:
    repo = FakeDiscoveryRepository()
    service = _service(repo)
    with pytest.raises(CompetitorTopicsParseError):
        await service.ingest_sources(
            [("only-catalog.txt", b"https://promatras.by/catalog\n")],
            CompetitorTopicsSourcesRequest(),
        )
    assert repo.plans == {}
