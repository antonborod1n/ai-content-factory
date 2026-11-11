"""Orchestrate competitor SERP research → structure → improved outline."""

from __future__ import annotations

import logging
import uuid

from app.config import get_settings
from app.core.competitor_brief import (
    CompetitorCounts,
    brief_stats_from_competitors,
)
from app.core.competitor_filter import (
    DEFAULT_MIN_ARTICLE_CHARS,
    is_competitor_article_url,
    is_usable_competitor_article,
)
from app.core.exceptions import (
    INTERRUPTED_MESSAGE,
    AIError,
    ResearchConfigurationError,
    ResearchError,
    ResearchNotFoundError,
    ResearchUpstreamError,
)
from app.core.page_structure import parse_html
from app.core.section_images import allocate_section_images
from app.db.models.research import ResearchRun, ResearchStatus
from app.repositories.research_repository import ResearchRepository
from app.schemas.ai import (
    ArticleWriteInput,
    CompetitorPlanOutput,
    CompetitorSourceRef,
    SectionImageCount,
)
from app.schemas.research import (
    CompetitorPlanInput,
    CompetitorProfile,
    ResearchRequest,
    SearchHit,
    format_competitor_context,
)
from app.services.ai.analyst import CompetitorAnalyst
from app.services.research.page_fetcher import PageFetcher
from app.services.research.searcher import SearchProvider
from app.services.run_tracker import RunTracker

logger = logging.getLogger(__name__)


class ResearchService:
    """Search → fetch/parse → outline plan → persist. No HTTP in this class."""

    def __init__(
        self,
        repository: ResearchRepository,
        searcher: SearchProvider,
        fetcher: PageFetcher,
        analyst: CompetitorAnalyst,
        *,
        enabled: bool | None = None,
        top_n: int | None = None,
        search_n: int | None = None,
        min_article_chars: int | None = None,
        default_word_count: int | None = None,
        run_tracker: RunTracker | None = None,
    ) -> None:
        settings = get_settings()
        self._repository = repository
        self._searcher = searcher
        self._fetcher = fetcher
        self._analyst = analyst
        self._enabled = settings.research_enabled if enabled is None else enabled
        self._top_n = settings.research_top_n if top_n is None else top_n
        self._search_n = settings.research_search_n if search_n is None else search_n
        self._min_article_chars = (
            settings.research_min_article_chars
            if min_article_chars is None
            else min_article_chars
        )
        self._default_word_count = (
            settings.article_target_word_count
            if default_word_count is None
            else default_word_count
        )
        self._runs = run_tracker or RunTracker()

    async def analyze(self, request: ResearchRequest) -> ResearchRun:
        """Run the full Stage 3 research pipeline and persist the result."""
        if not self._enabled:
            raise ResearchConfigurationError("Competitor research is disabled")

        query = _search_query(request)
        top_n = request.top_n or self._top_n
        search_n = min(100, max(top_n, self._search_n))
        run = await self._repository.create(
            topic=request.topic,
            language=request.language,
            audience=request.audience,
            query=query,
            status=ResearchStatus.PROCESSING,
        )
        track_id = await self._runs.start(
            "competitor",
            {
                "topic": request.topic,
                "language": request.language,
                "audience": request.audience,
                "query": query,
                "top_n": top_n,
            },
        )
        history_output: dict[str, object] | None = None
        try:
            async with self._runs.step(track_id, "search") as handle:
                hits = await self._searcher.search(query, top_n=search_n)
                handle.detail = {"results": len(hits)}
                if not hits:
                    raise ResearchUpstreamError("Search returned no results")
            async with self._runs.step(track_id, "fetch") as handle:
                profiles = await self._profiles_from_hits(hits, top_n=top_n)
                handle.detail = {"articles": len(profiles)}
                if not profiles:
                    raise ResearchUpstreamError(
                        "No suitable competitor articles in search results"
                    )
            async with self._runs.step(track_id, "outline") as handle:
                plan = await self._plan_outline(request, profiles)
                section_slots = _section_slots_for_outline(plan.outline, profiles)
                rows = [_competitor_row(profile) for profile in profiles]
                await self._repository.add_competitors(run.id, rows)
                updated = await self._repository.update(
                    run.id,
                    status=ResearchStatus.COMPLETED,
                    outline=plan.outline,
                    section_image_placeholders=section_slots,
                    title_hint=plan.title_hint,
                    meta_description_hint=plan.meta_description_hint,
                    url_slug_hint=plan.url_slug_hint,
                    article_goal=plan.article_goal,
                    notes=plan.notes,
                    error_message=None,
                )
                if updated is None:
                    raise ResearchError("Research run disappeared")
                handle.detail = {
                    "sections": len(plan.outline),
                    "title": plan.title_hint,
                    "goal": plan.article_goal,
                }
            logger.info(
                "Research completed id=%s competitors=%s outline=%s",
                updated.id,
                len(profiles),
                len(plan.outline),
            )
            history_output = {
                "research_id": str(updated.id),
                "competitors": len(profiles),
                "outline": len(plan.outline),
                "title": plan.title_hint,
                "goal": plan.article_goal,
            }
            return updated
        except ResearchConfigurationError as exc:
            await self._mark_failed(run.id, exc.message)
            raise
        except ResearchUpstreamError as exc:
            await self._mark_failed(run.id, exc.message)
            raise ResearchUpstreamError(exc.message, research_id=run.id) from exc
        except AIError as exc:
            await self._mark_failed(run.id, exc.message)
            raise ResearchUpstreamError(exc.message, research_id=run.id) from exc
        except ResearchError as exc:
            await self._mark_failed(run.id, exc.message)
            raise
        except Exception as exc:
            logger.exception("Unexpected error during competitor research")
            await self._mark_failed(run.id, "Competitor research failed")
            raise ResearchError(
                "Competitor research failed", research_id=run.id
            ) from exc
        except BaseException:
            await self._mark_interrupted(run.id)
            raise
        finally:
            await self._runs.finish_current(track_id, output_json=history_output)

    async def get(self, research_id: uuid.UUID) -> ResearchRun:
        run = await self._repository.get_by_id(research_id)
        if run is None:
            raise ResearchNotFoundError(research_id)
        return run

    async def list(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[ResearchRun], int]:
        items = await self._repository.list(limit=limit, offset=offset)
        total = await self._repository.count()
        return items, total

    async def attach_to_write_input(
        self, request: ArticleWriteInput
    ) -> ArticleWriteInput:
        """Load or run research and copy outline / volume / media onto the brief."""
        if request.research_id is None and not request.use_competitor_research:
            return request
        if not self._enabled:
            if request.research_id is None and request.use_competitor_research:
                raise ResearchConfigurationError("Competitor research is disabled")
            if request.research_id is None:
                return request

        if request.research_id is not None:
            run = await self.get(request.research_id)
            if run.status != ResearchStatus.COMPLETED:
                raise ResearchError(
                    "Research is not completed",
                    research_id=run.id,
                )
        else:
            run = await self.analyze(
                ResearchRequest(
                    topic=request.topic,
                    language=request.language,
                    audience=request.audience,
                    keywords=request.keywords_for_storage(),
                    word_count=request.word_count,
                )
            )

        profiles = [
            CompetitorProfile(
                rank=row.rank,
                title=row.title,
                url=row.url,
                snippet=row.snippet,
                headings=list(row.headings or []),
                section_images=_section_images_from_row(row.section_images),
                word_count=row.word_count,
                image_count=row.image_count,
                infographic_count=_infographic_count_from_features(row.features),
                video_count=row.video_count,
                list_count=row.list_count,
                table_count=row.table_count,
                has_faq=row.has_faq,
                features=list(row.features or []),
                fetch_status=row.fetch_status,
            )
            for row in run.competitors
        ]
        plan = CompetitorPlanOutput(
            outline=list(run.outline or []),
            title_hint=run.title_hint,
            meta_description_hint=run.meta_description_hint,
            url_slug_hint=run.url_slug_hint,
            article_goal=run.article_goal,
            notes=run.notes,
        )
        stored_slots = [
            max(0, int(item)) for item in (run.section_image_placeholders or [])
        ]
        section_slots = (
            stored_slots
            if len(stored_slots) == len(plan.outline)
            else _section_slots_for_outline(plan.outline, profiles)
        )
        updates: dict[str, object] = {
            "outline": plan.outline,
            "competitor_context": format_competitor_context(plan, profiles),
            "research_id": run.id,
            "competitor_sources": competitor_sources_from_profiles(profiles),
            "competitor_image_sections": [
                list(profile.section_images) for profile in profiles
            ],
        }
        if section_slots and sum(section_slots) > 0:
            updates["section_image_placeholders"] = section_slots
            updates["image_placeholders"] = sum(section_slots)
        if plan.article_goal.strip():
            updates["article_goal"] = plan.article_goal
        stats = brief_stats_from_competitors(
            [_counts_from_profile(item) for item in profiles]
        )
        if stats.word_count is not None:
            updates["word_count"] = stats.word_count
        updates["include_tables"] = stats.include_tables
        updates["include_lists"] = stats.include_lists
        updates["include_faq"] = stats.include_faq
        updates["faq_count"] = stats.faq_count
        updates["infographic_placeholders"] = stats.infographic_placeholders
        for key, value in updates.items():
            setattr(request, key, value)
        return request

    async def _profiles_from_hits(
        self, hits: list[SearchHit], *, top_n: int
    ) -> list[CompetitorProfile]:
        profiles: list[CompetitorProfile] = []
        skipped = 0
        min_chars = (
            self._min_article_chars
            if self._min_article_chars >= 0
            else DEFAULT_MIN_ARTICLE_CHARS
        )
        for hit in hits:
            if len(profiles) >= top_n:
                break
            if not is_competitor_article_url(hit.url):
                skipped += 1
                continue
            html = await self._fetcher.fetch(hit.url)
            if not html:
                skipped += 1
                continue
            structure = parse_html(html, fallback_title=hit.title)
            if not is_usable_competitor_article(
                structure, html=html, min_chars=min_chars
            ):
                skipped += 1
                continue
            profiles.append(
                CompetitorProfile(
                    rank=len(profiles) + 1,
                    title=structure.title or hit.title,
                    url=hit.url,
                    snippet=hit.snippet,
                    headings=structure.headings,
                    section_images=[
                        SectionImageCount(
                            heading=item.heading,
                            image_count=item.image_count,
                        )
                        for item in structure.sections
                    ],
                    word_count=structure.word_count,
                    image_count=structure.image_count,
                    infographic_count=structure.infographic_count,
                    video_count=structure.video_count,
                    list_count=structure.list_count,
                    table_count=structure.table_count,
                    has_faq=structure.has_faq,
                    features=structure.features,
                    fetch_status="fetched",
                )
            )
        logger.info(
            "Research competitor filter kept=%s skipped=%s",
            len(profiles),
            skipped,
        )
        return profiles

    async def _plan_outline(
        self, request: ResearchRequest, profiles: list[CompetitorProfile]
    ) -> CompetitorPlanOutput:
        stats = brief_stats_from_competitors(
            [_counts_from_profile(item) for item in profiles]
        )
        word_count = stats.word_count or request.word_count or self._default_word_count
        try:
            return await self._analyst.plan(
                CompetitorPlanInput(
                    topic=request.topic,
                    language=request.language,
                    audience=request.audience,
                    keywords=request.keywords,
                    word_count=word_count,
                    competitors=profiles,
                )
            )
        except AIError:
            logger.warning("Analyst failed; using heading fallback outline")
            return _fallback_plan(request.topic, request.language, profiles)

    async def _mark_interrupted(self, research_id: uuid.UUID) -> None:
        current = await self._repository.get_by_id(research_id)
        if current is None or current.status not in {
            ResearchStatus.PENDING,
            ResearchStatus.PROCESSING,
        }:
            return
        await self._mark_failed(research_id, INTERRUPTED_MESSAGE)

    async def _mark_failed(self, research_id: uuid.UUID, message: str) -> None:
        try:
            await self._repository.update(
                research_id,
                status=ResearchStatus.FAILED,
                error_message=message,
            )
        except Exception:
            logger.exception("Could not mark research %s as failed", research_id)


def competitor_sources_from_profiles(
    profiles: list[CompetitorProfile],
) -> list[CompetitorSourceRef]:
    """Unique competitor URLs in rank order. No page bodies."""
    seen: set[str] = set()
    sources: list[CompetitorSourceRef] = []
    for profile in sorted(profiles, key=lambda item: item.rank):
        url = profile.url.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append(
            CompetitorSourceRef(
                rank=profile.rank,
                title=profile.title.strip(),
                url=url,
            )
        )
    return sources


def _search_query(request: ResearchRequest) -> str:
    parts = [request.topic, *request.keywords]
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        cleaned = part.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return " ".join(unique)


def _competitor_row(profile: CompetitorProfile) -> dict[str, object]:
    return {
        "rank": profile.rank,
        "title": profile.title,
        "url": profile.url,
        "snippet": profile.snippet,
        "headings": profile.headings,
        "section_images": [
            item.model_dump(mode="json") for item in profile.section_images
        ],
        "word_count": profile.word_count,
        "image_count": profile.image_count,
        "video_count": profile.video_count,
        "list_count": profile.list_count,
        "table_count": profile.table_count,
        "has_faq": profile.has_faq,
        "features": profile.features,
        "fetch_status": profile.fetch_status,
    }


def _fallback_plan(
    topic: str,
    language: str,
    profiles: list[CompetitorProfile],
) -> CompetitorPlanOutput:
    seen: set[str] = set()
    outline: list[str] = []
    for profile in profiles:
        for heading in profile.headings:
            key = heading.casefold()
            if len(heading) < 4 or key in seen:
                continue
            seen.add(key)
            outline.append(heading)
            if len(outline) >= 8:
                break
        if len(outline) >= 8:
            break
    extras = (
        ("FAQ", "Заключение")
        if language.lower().startswith("ru")
        else ("FAQ", "Conclusion")
    )
    for extra in extras:
        if extra.casefold() not in seen:
            outline.append(extra)
    if len(outline) < 2:
        outline = ["Введение", "Основная часть", "FAQ", "Заключение"]
    return CompetitorPlanOutput(
        outline=outline[:10],
        title_hint=topic,
        notes="Outline assembled from competitor headings (analyst fallback)",
    )


def _section_images_from_row(raw: object) -> list[SectionImageCount]:
    if not isinstance(raw, list):
        return []
    parsed: list[SectionImageCount] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading") or "").strip()
        try:
            count = int(item.get("image_count") or 0)
        except (TypeError, ValueError):
            count = 0
        parsed.append(SectionImageCount(heading=heading, image_count=max(0, count)))
    return parsed


def _counts_from_profile(profile: CompetitorProfile) -> CompetitorCounts:
    return CompetitorCounts(
        word_count=profile.word_count,
        list_count=profile.list_count,
        table_count=profile.table_count,
        has_faq=profile.has_faq,
        infographic_count=(
            profile.infographic_count
            or _infographic_count_from_features(profile.features)
        ),
    )


def _infographic_count_from_features(raw: object) -> int:
    if not isinstance(raw, list):
        return 0
    for item in raw:
        text = str(item)
        if not text.startswith("infographics:"):
            continue
        try:
            return max(0, int(text.split(":", 1)[1]))
        except (TypeError, ValueError, IndexError):
            return 0
    return 0


def _section_slots_for_outline(
    outline: list[str], profiles: list[CompetitorProfile]
) -> list[int]:
    usable = [item for item in profiles if item.fetch_status == "fetched"] or profiles
    pages = [
        [(item.heading, item.image_count) for item in profile.section_images]
        for profile in usable
    ]
    totals = [profile.image_count for profile in usable]
    return allocate_section_images(outline, pages, page_totals=totals)
