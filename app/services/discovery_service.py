"""Topic Discovery: SERP snapshots → clustered briefs → topics file export."""

from __future__ import annotations

import logging
import uuid

from app.config import get_settings
from app.core.exceptions import (
    AIError,
    DiscoveryConfigurationError,
    DiscoveryError,
    DiscoveryNotFoundError,
    DiscoveryUpstreamError,
)
from app.core.topic_candidates import dedupe_candidates, is_near_duplicate
from app.core.topics_file import TopicsMergeResult, dump_topic_brief, merge_topics
from app.db.models.discovery import ContentPlan, ContentPlanSource, ContentPlanStatus
from app.repositories.discovery_repository import DiscoveryRepository
from app.schemas.articles import ArticleGenerateRequest
from app.schemas.discovery import (
    CandidateKind,
    DiscoveryExportResponse,
    DiscoveryRequest,
    SearchEngine,
    SerpSnapshot,
    TopicBriefDraft,
    TopicCandidate,
    TopicPlanInput,
)
from app.services.ai.topic_planner import TopicPlanner
from app.services.discovery.snapshotter import SerpSnapshotProvider
from app.services.run_tracker import RunTracker

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Snapshot → flatten/dedupe → plan briefs → persist. No HTTP in this class."""

    def __init__(
        self,
        repository: DiscoveryRepository,
        snapshotter: SerpSnapshotProvider,
        planner: TopicPlanner,
        *,
        enabled: bool | None = None,
        max_topics: int | None = None,
        search_n: int | None = None,
        topics_file_path: str | None = None,
        default_word_count: int | None = None,
        run_tracker: RunTracker | None = None,
    ) -> None:
        settings = get_settings()
        self._repository = repository
        self._snapshotter = snapshotter
        self._planner = planner
        self._enabled = settings.discovery_enabled if enabled is None else enabled
        self._max_topics = (
            settings.discovery_max_topics if max_topics is None else max_topics
        )
        self._search_n = (
            settings.discovery_search_n if search_n is None else search_n
        )
        self._topics_file_path = (
            settings.topics_file_path
            if topics_file_path is None
            else topics_file_path
        )
        self._default_word_count = (
            settings.article_target_word_count
            if default_word_count is None
            else default_word_count
        )
        self._runs = run_tracker or RunTracker()

    async def discover(self, request: DiscoveryRequest) -> ContentPlan:
        if not self._enabled:
            raise DiscoveryConfigurationError("Topic discovery is disabled")
        google_on = SearchEngine.GOOGLE in request.engines
        google_ready = self._snapshotter.is_configured(SearchEngine.GOOGLE)
        if google_on and not google_ready:
            raise DiscoveryConfigurationError("SERP API key is not configured")

        max_topics = min(request.max_topics or self._max_topics, 30)
        plan = await self._repository.create(
            niche=request.niche,
            seeds=request.seeds,
            language=request.language,
            audience=request.audience,
            status=ContentPlanStatus.PROCESSING,
            source=ContentPlanSource.SERP.value,
        )
        run_id = await self._runs.start(
            "discovery",
            {
                "plan_id": str(plan.id),
                "niche": request.niche,
                "seeds": list(request.seeds)[:20],
                "language": request.language,
                "audience": request.audience,
            },
        )
        history_output: dict[str, object] | None = None
        try:
            async with self._runs.step(run_id, "snapshots") as handle:
                snapshots, engines_used = await self._collect_snapshots(request)
                handle.detail = {
                    "engines": [engine.value for engine in engines_used],
                    "snapshots": len(snapshots),
                }
            async with self._runs.step(run_id, "candidates") as handle:
                candidates = dedupe_candidates(flatten_candidates(snapshots))
                await self._repository.update(
                    plan.id,
                    engines_used=[engine.value for engine in engines_used],
                    candidates=[item.model_dump(mode="json") for item in candidates],
                )
                handle.detail = {"candidates": len(candidates)}
                if not candidates:
                    raise DiscoveryUpstreamError(
                        "Search provider returned no candidates"
                    )
            async with self._runs.step(run_id, "briefs") as handle:
                drafts = await self._plan_briefs(request, candidates, max_topics)
                rows = [
                    {
                        "sort_order": index,
                        "brief": dump_topic_brief(
                            self._to_generate_request(draft, request)
                        ),
                        "source_engines": sources[0],
                        "source_queries": sources[1],
                    }
                    for index, draft in enumerate(drafts)
                    for sources in [
                        self._sources_for(draft, candidates, request.seeds)
                    ]
                ]
                await self._repository.add_topics(plan.id, rows)
                updated = await self._repository.update(
                    plan.id,
                    status=ContentPlanStatus.COMPLETED,
                    error_message=None,
                )
                titles = [draft.topic for draft in drafts][:30]
                handle.detail = {"topics": len(drafts), "titles": titles}
            logger.info(
                "Discovery completed plan_id=%s topics=%s candidates=%s engines=%s",
                plan.id,
                len(drafts),
                len(candidates),
                [engine.value for engine in engines_used],
            )
            assert updated is not None
            history_output = {
                "plan_id": str(updated.id),
                "topics": len(drafts),
                "candidates": len(candidates),
                "titles": [draft.topic for draft in drafts][:30],
            }
            return updated
        except (DiscoveryConfigurationError, DiscoveryUpstreamError, DiscoveryError):
            await self._fail(plan.id, "Topic discovery failed")
            raise
        except AIError as exc:
            await self._fail(plan.id, "Topic planner failed")
            raise DiscoveryUpstreamError("Topic planner failed") from exc
        except Exception as exc:
            await self._fail(plan.id, "Topic discovery failed")
            raise DiscoveryError("Topic discovery failed", plan_id=plan.id) from exc
        finally:
            await self._runs.finish_current(run_id, output_json=history_output)

    async def get(self, plan_id: uuid.UUID) -> ContentPlan:
        plan = await self._repository.get_by_id(plan_id)
        if plan is None:
            raise DiscoveryNotFoundError(plan_id)
        return plan

    async def list(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[ContentPlan], int]:
        items = await self._repository.list(
            limit=limit,
            offset=offset,
            source=ContentPlanSource.SERP.value,
        )
        total = await self._repository.count(source=ContentPlanSource.SERP.value)
        return items, total

    async def export(
        self,
        plan_id: uuid.UUID,
        *,
        path: str | None = None,
    ) -> DiscoveryExportResponse:
        run_id = await self._runs.start(
            "topics_export",
            {"plan_id": str(plan_id), "kind": "discovery"},
        )
        history_output: dict[str, object] | None = None
        try:
            plan = await self.get(plan_id)
            if plan.status != ContentPlanStatus.COMPLETED:
                raise DiscoveryError(
                    "Content plan is not completed",
                    plan_id=plan_id,
                )
            dest = (path or self._topics_file_path or "").strip()
            if not dest:
                raise DiscoveryConfigurationError("Topics file path is not configured")
            briefs = [row.brief for row in plan.topics]
            result = self._merge(dest, briefs)
            logger.info(
                "Discovery exported plan_id=%s added=%s skipped=%s",
                plan_id,
                result.added,
                result.skipped,
            )
            history_output = {
                "path": str(result.path),
                "added": result.added,
                "skipped": result.skipped,
            }
            return DiscoveryExportResponse(
                path=str(result.path),
                added=result.added,
                skipped=result.skipped,
            )
        finally:
            await self._runs.finish_current(run_id, output_json=history_output)

    def _merge(self, dest: str, briefs: list[object]) -> TopicsMergeResult:
        payloads = [item if isinstance(item, dict) else {} for item in briefs]
        return merge_topics(dest, payloads)

    async def _collect_snapshots(
        self, request: DiscoveryRequest
    ) -> tuple[list[SerpSnapshot], list[SearchEngine]]:
        snapshots: list[SerpSnapshot] = []
        engines_used: list[SearchEngine] = []
        for engine in request.engines:
            if not self._snapshotter.is_configured(engine):
                if engine == SearchEngine.GOOGLE:
                    raise DiscoveryConfigurationError("SERP API key is not configured")
                logger.info("Skipping %s snapshot: provider is not configured", engine)
                continue
            engines_used.append(engine)
            for seed in request.seeds:
                snapshot = await self._snapshotter.snapshot(
                    seed,
                    engine=engine,
                    top_n=self._search_n,
                )
                snapshots.append(snapshot)
        return snapshots, engines_used

    async def _plan_briefs(
        self,
        request: DiscoveryRequest,
        candidates: list[TopicCandidate],
        max_topics: int,
    ) -> list[TopicBriefDraft]:
        planned = await self._planner.plan(
            TopicPlanInput(
                niche=request.niche,
                seeds=request.seeds,
                language=request.language,
                audience=request.audience,
                max_topics=max_topics,
                candidates=candidates,
            )
        )
        drafts = [item for item in planned.topics if item.topic.strip()][:max_topics]
        if drafts:
            return drafts
        return _fallback_briefs(candidates, request.seeds, max_topics)

    def _to_generate_request(
        self, draft: TopicBriefDraft, request: DiscoveryRequest
    ) -> ArticleGenerateRequest:
        primary = list(draft.primary_keywords) or [draft.topic]
        return ArticleGenerateRequest(
            topic=draft.topic,
            language=request.language,
            audience=request.audience,
            keywords=primary,
            primary_keywords=primary,
            secondary_keywords=list(draft.secondary_keywords),
            article_goal=draft.article_goal,
            outline=list(draft.outline),
            search_intent=draft.search_intent or request.search_intent,
            word_count=request.word_count or self._default_word_count,
            tone=request.tone,
            use_knowledge_base=request.use_knowledge_base,
            use_competitor_research=request.use_competitor_research,
            use_multi_agent=request.use_multi_agent,
            use_text=request.use_text,
            use_images=request.use_images,
            use_internal_links=request.use_internal_links,
            use_dzen=request.use_dzen,
            use_detectors=request.use_detectors,
            use_humanizer=request.use_humanizer,
            use_summary=request.use_summary,
        )

    def _sources_for(
        self,
        draft: TopicBriefDraft,
        candidates: list[TopicCandidate],
        seeds: list[str],
    ) -> tuple[list[str], list[str]]:
        engines: list[str] = []
        queries: list[str] = []
        seen_engines: set[str] = set()
        seen_queries: set[str] = set()
        for candidate in candidates:
            related = [candidate.text, *draft.primary_keywords]
            if not (
                is_near_duplicate(draft.topic, related, threshold=0.3)
                or is_near_duplicate(candidate.text, [draft.topic], threshold=0.3)
            ):
                continue
            if candidate.engine.value not in seen_engines:
                seen_engines.add(candidate.engine.value)
                engines.append(candidate.engine.value)
            if candidate.query not in seen_queries:
                seen_queries.add(candidate.query)
                queries.append(candidate.query)
        if not engines:
            engines = sorted({item.engine.value for item in candidates})
        if not queries:
            queries = list(seeds)
        return engines, queries

    async def _fail(self, plan_id: uuid.UUID, message: str) -> None:
        try:
            await self._repository.update(
                plan_id,
                status=ContentPlanStatus.FAILED,
                error_message=message,
            )
        except Exception:
            logger.exception("Failed to mark content plan as failed")


def flatten_candidates(snapshots: list[SerpSnapshot]) -> list[TopicCandidate]:
    """Organic titles + PAA + related from snapshots. No HTTP."""
    candidates: list[TopicCandidate] = []
    for snapshot in snapshots:
        query = snapshot.query
        engine = snapshot.engine
        for hit in snapshot.organic:
            title = hit.title.strip()
            if not title:
                continue
            candidates.append(
                TopicCandidate(
                    text=title,
                    kind=CandidateKind.ORGANIC,
                    engine=engine,
                    query=query,
                    url=hit.url,
                )
            )
        for question in snapshot.people_also_ask:
            text = question.strip()
            if not text:
                continue
            candidates.append(
                TopicCandidate(
                    text=text,
                    kind=CandidateKind.PAA,
                    engine=engine,
                    query=query,
                )
            )
        for related in snapshot.related_searches:
            text = related.strip()
            if not text:
                continue
            candidates.append(
                TopicCandidate(
                    text=text,
                    kind=CandidateKind.RELATED,
                    engine=engine,
                    query=query,
                )
            )
    return candidates


def _fallback_briefs(
    candidates: list[TopicCandidate],
    seeds: list[str],
    max_topics: int,
) -> list[TopicBriefDraft]:
    texts: list[str] = []
    for item in candidates:
        if item.kind in {CandidateKind.ORGANIC, CandidateKind.PAA}:
            texts.append(item.text)
    if not texts:
        texts = list(seeds)
    drafts: list[TopicBriefDraft] = []
    for text in texts:
        drafts.append(
            TopicBriefDraft(
                topic=text,
                primary_keywords=[text],
                article_goal=f"Раскрыть тему: {text}",
                outline=[
                    "Что важно знать",
                    "Как выбрать",
                    "Типичные ошибки",
                    "FAQ",
                    "Заключение",
                ],
            )
        )
        if len(drafts) >= max_topics:
            break
    return drafts
