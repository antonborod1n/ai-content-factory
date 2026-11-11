"""Import competitor-inventory content plans into topics.json."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from app.config import get_settings
from app.core.competitor_plan import (
    CompetitorPlan,
    CompetitorPlanTopic,
    is_content_plan_payload,
    plan_context,
    plan_to_topic_rows,
)
from app.core.competitor_sources import extract_topic_hits, parse_competitor_file
from app.core.exceptions import (
    AIError,
    CompetitorTopicsConfigurationError,
    CompetitorTopicsError,
    CompetitorTopicsNotFoundError,
    CompetitorTopicsParseError,
    CompetitorTopicsUpstreamError,
)
from app.core.topics_file import TopicsMergeResult, merge_topics
from app.db.models.discovery import ContentPlan, ContentPlanSource, ContentPlanStatus
from app.repositories.discovery_repository import DiscoveryRepository
from app.schemas.competitor_topics import (
    CompetitorTopicsExportResponse,
    CompetitorTopicsImportRequest,
    CompetitorTopicsSourcesRequest,
    ContentGapHit,
    ContentGapInput,
)
from app.services.ai.content_gap import ContentGapAnalyst
from app.services.run_tracker import RunTracker

logger = logging.getLogger(__name__)


class CompetitorTopicsService:
    """Map competitor dumps or a ready JSON plan to briefs. No HTTP in this class."""

    def __init__(
        self,
        repository: DiscoveryRepository,
        analyst: ContentGapAnalyst | None = None,
        *,
        enabled: bool | None = None,
        topics_file_path: str | None = None,
        max_topics: int | None = None,
        max_hits: int | None = None,
        run_tracker: RunTracker | None = None,
    ) -> None:
        settings = get_settings()
        self._repository = repository
        self._analyst = analyst
        self._enabled = (
            settings.competitor_topics_enabled if enabled is None else enabled
        )
        self._topics_file_path = (
            settings.topics_file_path
            if topics_file_path is None
            else topics_file_path
        )
        self._max_topics = (
            settings.competitor_topics_max_topics if max_topics is None else max_topics
        )
        self._max_hits = (
            settings.competitor_topics_max_hits if max_hits is None else max_hits
        )
        self._runs = run_tracker or RunTracker()

    async def import_plan(self, request: CompetitorTopicsImportRequest) -> ContentPlan:
        if not self._enabled:
            raise CompetitorTopicsConfigurationError(
                "Competitor topic import is disabled"
            )
        plan_input = request.to_plan()
        row = await self._repository.create(
            niche=plan_input.niche,
            seeds=[],
            language=request.language,
            audience=plan_input.audience,
            status=ContentPlanStatus.PROCESSING,
            source=ContentPlanSource.COMPETITOR_GAP.value,
            context=plan_context(plan_input),
        )
        run_id = await self._runs.start(
            "competitor_plan",
            {
                "plan_id": str(row.id),
                "domain": plan_input.domain,
                "niche": plan_input.niche,
                "language": request.language,
                "topics": len(plan_input.topics),
            },
        )
        history_output: dict[str, object] | None = None
        try:
            rows = plan_to_topic_rows(
                plan_input,
                language=request.language,
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
            await self._repository.add_topics(row.id, rows)
            updated = await self._repository.update(
                row.id,
                status=ContentPlanStatus.COMPLETED,
                error_message=None,
            )
            logger.info(
                "Competitor topics imported plan_id=%s topics=%s domain=%s",
                row.id,
                len(rows),
                plan_input.domain,
            )
            assert updated is not None
            titles = [
                str(item.get("brief", {}).get("topic") or "")
                for item in rows
                if isinstance(item.get("brief"), dict)
            ]
            history_output = {
                "plan_id": str(updated.id),
                "topics": len(rows),
                "titles": [title for title in titles if title][:30],
            }
            return updated
        except CompetitorTopicsError:
            await self._fail(row.id, "Competitor topic import failed")
            raise
        except Exception as exc:
            await self._fail(row.id, "Competitor topic import failed")
            raise CompetitorTopicsError(
                "Competitor topic import failed", plan_id=row.id
            ) from exc
        finally:
            await self._runs.finish_current(run_id, output_json=history_output)

    async def ingest_sources(
        self,
        files: list[tuple[str, bytes]],
        request: CompetitorTopicsSourcesRequest,
    ) -> ContentPlan:
        """Parse competitor dumps, analyze gaps, persist briefs."""
        if not self._enabled:
            raise CompetitorTopicsConfigurationError(
                "Competitor topic import is disabled"
            )
        if not files:
            raise CompetitorTopicsParseError("No competitor files uploaded")
        if len(files) == 1:
            imported = self._try_ready_plan(files[0], request)
            if imported is not None:
                return await self.import_plan(imported)
        if self._analyst is None:
            raise CompetitorTopicsConfigurationError(
                "Content-gap analyst is not configured"
            )

        run_id = await self._runs.start(
            "competitor_topics",
            {
                "domain": request.domain,
                "niche": request.niche,
                "language": request.language,
                "audience": request.audience,
                "files": [name for name, _data in files][:20],
            },
        )
        history_output: dict[str, object] | None = None
        row: ContentPlan | None = None
        try:
            async with self._runs.step(run_id, "parse") as handle:
                hits: list[ContentGapHit] = []
                source_names: list[str] = []
                for filename, data in files:
                    parsed = parse_competitor_file(data=data, filename=filename)
                    source_names.append(parsed.filename)
                    for hit in extract_topic_hits(parsed):
                        hits.append(
                            ContentGapHit(
                                text=hit.text,
                                competitor=hit.competitor,
                                kind=hit.kind,
                                url=hit.url,
                                source_file=hit.source_file,
                            )
                        )
                hits = hits[: self._max_hits]
                handle.detail = {"files": len(source_names), "hits": len(hits)}
                if not hits:
                    raise CompetitorTopicsParseError(
                        "No topics found in competitor files"
                    )

            max_topics = max(1, min(self._max_topics, 300))
            plan_input = CompetitorPlan(
                domain=request.domain,
                niche=request.niche,
                audience=request.audience or "general",
                geo=request.geo,
                site_type=request.site_type,
                blog_format=request.blog_format,
                topics=[],
            )
            context = plan_context(plan_input)
            context["source_files"] = source_names
            row = await self._repository.create(
                niche=plan_input.niche,
                seeds=[],
                language=request.language,
                audience=plan_input.audience,
                status=ContentPlanStatus.PROCESSING,
                source=ContentPlanSource.COMPETITOR_GAP.value,
                context=context,
            )
            async with self._runs.step(run_id, "analyze") as handle:
                await self._repository.update(
                    row.id,
                    candidates=[item.model_dump(mode="json") for item in hits],
                )
                analyzed = await self._analyst.analyze(
                    ContentGapInput(
                        domain=request.domain,
                        niche=request.niche,
                        audience=plan_input.audience,
                        geo=request.geo,
                        site_type=request.site_type,
                        language=request.language,
                        max_topics=max_topics,
                        hits=hits,
                    )
                )
                topics = [
                    item for item in analyzed.topics if item.title.strip()
                ][:max_topics]
                if not topics:
                    topics = _fallback_topics(hits, request.domain, max_topics)
                handle.detail = {"topics": len(topics)}
            plan_input = CompetitorPlan(
                domain=request.domain,
                niche=request.niche,
                audience=plan_input.audience,
                geo=request.geo,
                site_type=request.site_type,
                blog_format=request.blog_format,
                topics=topics,
            )
            async with self._runs.step(run_id, "save") as handle:
                rows = plan_to_topic_rows(
                    plan_input,
                    language=request.language,
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
                await self._repository.add_topics(row.id, rows)
                updated = await self._repository.update(
                    row.id,
                    status=ContentPlanStatus.COMPLETED,
                    error_message=None,
                )
                titles = [topic.title for topic in topics][:30]
                handle.detail = {"topics": len(rows), "titles": titles}
            logger.info(
                "Competitor sources ingested plan_id=%s topics=%s hits=%s",
                row.id,
                len(rows),
                len(hits),
            )
            assert updated is not None
            history_output = {
                "plan_id": str(updated.id),
                "topics": len(rows),
                "hits": len(hits),
                "titles": [topic.title for topic in topics][:30],
            }
            return updated
        except CompetitorTopicsError:
            if row is not None:
                await self._fail(row.id, "Competitor topic import failed")
            raise
        except AIError as exc:
            if row is not None:
                await self._fail(row.id, "Content-gap analyst failed")
            raise CompetitorTopicsUpstreamError(
                "Content-gap analyst failed",
                plan_id=row.id if row is not None else None,
            ) from exc
        except Exception as exc:
            if row is not None:
                await self._fail(row.id, "Competitor topic import failed")
            raise CompetitorTopicsError(
                "Competitor topic import failed",
                plan_id=row.id if row is not None else None,
            ) from exc
        finally:
            await self._runs.finish_current(run_id, output_json=history_output)

    def _try_ready_plan(
        self,
        file: tuple[str, bytes],
        request: CompetitorTopicsSourcesRequest,
    ) -> CompetitorTopicsImportRequest | None:
        filename, data = file
        if Path(filename).suffix.lower() != ".json":
            return None
        try:
            raw = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not is_content_plan_payload(raw):
            return None
        payload = dict(raw)
        if request.domain:
            payload["domain"] = request.domain
        if request.niche:
            payload["niche"] = request.niche
        if request.audience:
            payload["audience"] = request.audience
        if request.geo:
            payload["geo"] = request.geo
        payload.setdefault("language", request.language)
        payload.setdefault("use_knowledge_base", request.use_knowledge_base)
        payload.setdefault(
            "use_competitor_research", request.use_competitor_research
        )
        return CompetitorTopicsImportRequest.model_validate(payload)

    async def get(self, plan_id: uuid.UUID) -> ContentPlan:
        plan = await self._repository.get_by_id(plan_id)
        if plan is None or plan.source != ContentPlanSource.COMPETITOR_GAP.value:
            raise CompetitorTopicsNotFoundError(plan_id)
        return plan

    async def list(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[ContentPlan], int]:
        items = await self._repository.list(
            limit=limit,
            offset=offset,
            source=ContentPlanSource.COMPETITOR_GAP.value,
        )
        total = await self._repository.count(
            source=ContentPlanSource.COMPETITOR_GAP.value
        )
        return items, total

    async def export(
        self,
        plan_id: uuid.UUID,
        *,
        path: str | None = None,
    ) -> CompetitorTopicsExportResponse:
        run_id = await self._runs.start(
            "topics_export",
            {"plan_id": str(plan_id), "kind": "competitor"},
        )
        history_output: dict[str, object] | None = None
        try:
            plan = await self.get(plan_id)
            if plan.status != ContentPlanStatus.COMPLETED:
                raise CompetitorTopicsError(
                    "Content plan is not completed",
                    plan_id=plan_id,
                )
            dest = (path or self._topics_file_path or "").strip()
            if not dest:
                raise CompetitorTopicsConfigurationError(
                    "Topics file path is not configured"
                )
            briefs = [row.brief for row in plan.topics]
            payloads = [item if isinstance(item, dict) else {} for item in briefs]
            result = self._merge(dest, payloads)
            logger.info(
                "Competitor topics exported plan_id=%s added=%s skipped=%s",
                plan_id,
                result.added,
                result.skipped,
            )
            history_output = {
                "path": str(result.path),
                "added": result.added,
                "skipped": result.skipped,
            }
            return CompetitorTopicsExportResponse(
                path=str(result.path),
                added=result.added,
                skipped=result.skipped,
            )
        finally:
            await self._runs.finish_current(run_id, output_json=history_output)

    def _merge(self, dest: str, briefs: list[dict]) -> TopicsMergeResult:
        return merge_topics(dest, briefs)

    async def _fail(self, plan_id: uuid.UUID, message: str) -> None:
        await self._repository.update(
            plan_id,
            status=ContentPlanStatus.FAILED,
            error_message=message,
        )


def _fallback_topics(
    hits: list[ContentGapHit], domain: str, max_topics: int
) -> list[CompetitorPlanTopic]:
    unique: dict[str, ContentGapHit] = {}
    for hit in hits:
        unique.setdefault(hit.text, hit)
    topics: list[CompetitorPlanTopic] = []
    for text, hit in list(unique.items())[:max_topics]:
        owners = [hit.competitor] if hit.competitor else []
        topics.append(
            CompetitorPlanTopic(
                title=text,
                competitors=owners,
                is_gap=not owners,
                unique_angle="",
                intent="informational / howto",
                commercial_link=domain,
            )
        )
    return topics
