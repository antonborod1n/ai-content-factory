"""Stage 4 multi-agent orchestration: research → SEO → writer → fact-check → editor."""

from __future__ import annotations

import logging
import uuid

from app.config import get_settings
from app.core.exceptions import AIConfigurationError, ResearchConfigurationError
from app.core.section_images import allocate_section_images
from app.core.word_count import count_words
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.schemas.pipeline import (
    EditorInput,
    FactCheckInput,
    FactCheckOutput,
    PipelineStepName,
    PipelineStepStatus,
    PipelineStepTrace,
    PipelineTrace,
    SeoPlanInput,
    SeoPlanOutput,
    format_seo_context,
)
from app.services.ai.base import AIWriter
from app.services.ai.editor import Editor
from app.services.ai.fact_checker import FactChecker
from app.services.ai.seo_agent import SeoAgent
from app.services.rag_service import RagService
from app.services.research_service import ResearchService
from app.services.run_tracker import RunTracker

logger = logging.getLogger(__name__)


class PipelineService:
    """Runs the Stage 4 agent chain. No OpenAI SDK and no SQL here."""

    def __init__(
        self,
        writer: AIWriter,
        seo_agent: SeoAgent,
        fact_checker: FactChecker,
        editor: Editor,
        *,
        rag_service: RagService | None = None,
        research_service: ResearchService | None = None,
        run_tracker: RunTracker | None = None,
        enabled: bool | None = None,
        default_word_count: int | None = None,
    ) -> None:
        settings = get_settings()
        self._writer = writer
        self._seo_agent = seo_agent
        self._fact_checker = fact_checker
        self._editor = editor
        self._rag_service = rag_service
        self._research_service = research_service
        self._runs = run_tracker or RunTracker()
        self._enabled = settings.multi_agent_enabled if enabled is None else enabled
        self._default_word_count = (
            settings.article_target_word_count
            if default_word_count is None
            else default_word_count
        )

    async def run(
        self,
        request: ArticleWriteInput,
        *,
        run_id: uuid.UUID | None = None,
    ) -> tuple[AIArticleOutput, PipelineTrace]:
        """Execute the five-step chain and return the edited article + trace."""
        if not self._enabled:
            raise AIConfigurationError("Multi-agent pipeline is disabled")

        steps: list[PipelineStepTrace] = []
        async with self._runs.step(run_id, "research") as handle:
            request, research_step = await self._research(request)
            handle.status = research_step.status.value
            handle.detail = {
                "research_id": (
                    str(request.research_id) if request.research_id else None
                ),
                "note": research_step.notes,
            }
        steps.append(research_step)

        async with self._runs.step(run_id, "seo") as handle:
            request, seo_step = await self._seo(request)
            handle.detail = {
                "outline": len(request.outline),
                "intent": request.search_intent,
            }
        steps.append(seo_step)

        async with self._runs.step(run_id, "knowledge") as handle:
            request = await self._attach_knowledge_context(request)
            attached = bool(request.knowledge_context.strip())
            handle.detail = {"attached": attached}
            if not attached:
                handle.skip()
        async with self._runs.step(run_id, "writer") as handle:
            draft = await self._writer.generate(request)
            handle.detail = {
                "title": draft.title,
                "words": count_words(draft.content_markdown),
                "slug": draft.url_slug,
            }
        steps.append(
            PipelineStepTrace(
                name=PipelineStepName.WRITER,
                status=PipelineStepStatus.COMPLETED,
            )
        )
        logger.info(
            "Writer agent finished words=%s",
            count_words(draft.content_markdown),
        )

        async with self._runs.step(run_id, "fact_checker") as handle:
            fact_check, fact_step = await self._fact_check(request, draft)
            handle.detail = {
                "verdict": fact_check.verdict,
                "issues": len(fact_check.issues),
            }
        steps.append(fact_step)

        async with self._runs.step(run_id, "editor") as handle:
            edited = await self._editor.edit(
                EditorInput(
                    topic=request.topic,
                    language=request.language,
                    audience=request.audience,
                    outline=list(request.outline),
                    knowledge_context=request.knowledge_context,
                    competitor_context=request.competitor_context,
                    draft=draft,
                    fact_check=fact_check,
                )
            )
            handle.detail = {
                "title": edited.title,
                "words": count_words(edited.content_markdown),
                "slug": edited.url_slug,
            }
        steps.append(
            PipelineStepTrace(
                name=PipelineStepName.EDITOR,
                status=PipelineStepStatus.COMPLETED,
            )
        )
        logger.info(
            "Editor agent finished words=%s fact_verdict=%s",
            count_words(edited.content_markdown),
            fact_check.verdict,
        )
        return edited, PipelineTrace(enabled=True, steps=steps)

    async def _research(
        self, request: ArticleWriteInput
    ) -> tuple[ArticleWriteInput, PipelineStepTrace]:
        if self._research_service is None:
            return request, PipelineStepTrace(
                name=PipelineStepName.RESEARCH,
                status=PipelineStepStatus.SKIPPED,
                notes="research service not wired",
            )
        try:
            if request.research_id is None and not request.use_competitor_research:
                request.use_competitor_research = True
            updated = await self._research_service.attach_to_write_input(request)
        except ResearchConfigurationError as exc:
            logger.info("Research agent skipped: %s", exc.message)
            return request, PipelineStepTrace(
                name=PipelineStepName.RESEARCH,
                status=PipelineStepStatus.SKIPPED,
                notes="research not configured",
            )
        if not updated.competitor_context and updated.research_id is None:
            return request, PipelineStepTrace(
                name=PipelineStepName.RESEARCH,
                status=PipelineStepStatus.SKIPPED,
                notes="research not attached",
            )
        logger.info("Research agent finished research_id=%s", updated.research_id)
        return updated, PipelineStepTrace(
            name=PipelineStepName.RESEARCH,
            status=PipelineStepStatus.COMPLETED,
        )

    async def _seo(
        self, request: ArticleWriteInput
    ) -> tuple[ArticleWriteInput, PipelineStepTrace]:
        plan = await self._seo_agent.plan(
            SeoPlanInput(
                topic=request.topic,
                language=request.language,
                audience=request.audience,
                keywords=list(request.keywords),
                primary_keywords=list(request.primary_keywords),
                secondary_keywords=list(request.secondary_keywords),
                search_intent=request.search_intent,
                article_goal=request.article_goal,
                outline=list(request.outline),
                word_count=request.word_count or self._default_word_count,
                competitor_context=request.competitor_context,
            )
        )
        updated = _apply_seo_plan(request, plan)
        logger.info("SEO agent finished outline=%s", len(plan.outline))
        return updated, PipelineStepTrace(
            name=PipelineStepName.SEO,
            status=PipelineStepStatus.COMPLETED,
        )

    async def _attach_knowledge_context(
        self, request: ArticleWriteInput
    ) -> ArticleWriteInput:
        if self._rag_service is None:
            return request
        context = await self._rag_service.context_for_article(request)
        if not context:
            return request
        return request.model_copy(update={"knowledge_context": context})

    async def _fact_check(
        self, request: ArticleWriteInput, draft: AIArticleOutput
    ) -> tuple[FactCheckOutput, PipelineStepTrace]:
        report = await self._fact_checker.review(
            FactCheckInput(
                topic=request.topic,
                language=request.language,
                title=draft.title,
                meta_description=draft.meta_description,
                content_markdown=draft.content_markdown,
                knowledge_context=request.knowledge_context,
                competitor_context=request.competitor_context,
            )
        )
        logger.info(
            "Fact-check verdict=%s issues=%s",
            report.verdict,
            len(report.issues),
        )
        return report, PipelineStepTrace(
            name=PipelineStepName.FACT_CHECKER,
            status=PipelineStepStatus.COMPLETED,
            issue_count=len(report.issues),
            verdict=report.verdict,
        )


def _apply_seo_plan(
    request: ArticleWriteInput, plan: SeoPlanOutput
) -> ArticleWriteInput:
    updates: dict[str, object] = {"outline": list(plan.outline)}
    if plan.primary_keywords:
        updates["primary_keywords"] = list(plan.primary_keywords)
        updates["keywords"] = list(plan.primary_keywords)
    if plan.secondary_keywords:
        updates["secondary_keywords"] = list(plan.secondary_keywords)
    if plan.search_intent.strip():
        updates["search_intent"] = plan.search_intent.strip()
    if plan.article_goal.strip():
        updates["article_goal"] = plan.article_goal.strip()

    seo_block = format_seo_context(plan)
    existing = request.competitor_context.strip()
    updates["competitor_context"] = (
        f"{existing}\n\n{seo_block}" if existing else seo_block
    )
    pages = [
        [(item.heading, item.image_count) for item in page]
        for page in request.competitor_image_sections
    ]
    remapped = allocate_section_images(plan.outline, pages)
    if remapped and sum(remapped) > 0:
        updates["section_image_placeholders"] = remapped
        updates["image_placeholders"] = sum(remapped)
    return request.model_copy(update=updates)
