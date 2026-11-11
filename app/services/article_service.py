"""Article generation orchestration."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.config import get_settings
from app.core.article_file import resolve_article_media_path, try_save_article_to_file
from app.core.exceptions import (
    INTERRUPTED_MESSAGE,
    AIConfigurationError,
    AIError,
    ArticleGenerationError,
    ArticleGenerationUpstreamError,
    ArticleNotFoundError,
    ResearchConfigurationError,
    ResearchError,
    ResearchNotFoundError,
    ResearchUpstreamError,
)
from app.core.url_slug import normalize_url_slug
from app.core.word_count import count_words
from app.db.models.article import Article, ArticleStatus, ReviewStatus
from app.repositories.article_repository import ArticleRepository
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.schemas.dzen import DzenArticle, DzenWriteResult
from app.schemas.enrichment import GeneratedAsset, InternalLinkRef
from app.schemas.pipeline import PipelineTrace
from app.schemas.quality import QualityReport, QualityRunResult
from app.schemas.research import research_response
from app.services.ai.base import AIWriter
from app.services.dzen_service import DzenService
from app.services.image_service import ImageService
from app.services.linking_service import LinkingService
from app.services.pipeline_service import PipelineService
from app.services.quality_service import QualityService
from app.services.rag_service import RagService
from app.services.research_service import ResearchService
from app.services.run_tracker import RunTracker

logger = logging.getLogger(__name__)

_GENERIC_FAILURE_MESSAGE = "Article generation failed"


class ArticleService:
    """Owns article generation: optional research + RAG, then AI write, persist.

    When ``use_multi_agent`` is true, delegates to ``PipelineService``
    (research → SEO → writer → fact-check → editor). Stage 5 then optionally
    replaces image placeholders and inserts internal links. Stage 6 may run
    detectors / humanizer / summary, then a shorter Dzen version
    (``use_dzen``) from the polished title and body.
    """

    def __init__(
        self,
        repository: ArticleRepository,
        writer: AIWriter,
        *,
        rag_service: RagService | None = None,
        research_service: ResearchService | None = None,
        pipeline_service: PipelineService | None = None,
        image_service: ImageService | None = None,
        linking_service: LinkingService | None = None,
        dzen_service: DzenService | None = None,
        quality_service: QualityService | None = None,
        run_tracker: RunTracker | None = None,
        output_dir: Path | str | None = None,
    ) -> None:
        self._repository = repository
        self._writer = writer
        self._rag_service = rag_service
        self._research_service = research_service
        self._pipeline_service = pipeline_service
        self._image_service = image_service
        self._linking_service = linking_service
        self._dzen_service = dzen_service
        self._quality_service = quality_service
        self._runs = run_tracker or RunTracker()
        if output_dir is None:
            self._output_dir: Path | str | None = get_settings().articles_output_dir
        else:
            self._output_dir = output_dir

    async def get(self, article_id: uuid.UUID) -> Article:
        article = await self._repository.get_by_id(article_id)
        if article is None:
            raise ArticleNotFoundError(article_id)
        return article

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: ArticleStatus | None = None,
        review_status: ReviewStatus | None = None,
    ) -> tuple[list[Article], int]:
        items = await self._repository.list(
            limit=limit,
            offset=offset,
            status=status,
            review_status=review_status,
        )
        total = await self._repository.count(status=status, review_status=review_status)
        return items, total

    async def set_review(
        self, article_id: uuid.UUID, review_status: ReviewStatus
    ) -> Article:
        article = await self._repository.update(article_id, review_status=review_status)
        if article is None:
            raise ArticleNotFoundError(article_id)
        run_id = await self._runs.start(
            "review",
            {
                "article_id": str(article.id),
                "topic": article.topic,
                "review_status": review_status.value,
            },
        )
        await self._runs.finish(
            run_id,
            status="completed",
            output_json={
                "article_id": str(article.id),
                "review_status": review_status.value,
            },
            error=None,
        )
        return article

    async def generate(self, request: ArticleWriteInput) -> Article:
        """Generate an article and persist it.

        Flow: pending -> processing -> AI call -> validated output ->
        recalculated word_count -> completed (+ optional Markdown file).
        Any failure stores a safe error message and leaves the article failed.
        """
        if not request.use_text:
            if request.article_id is None:
                raise ArticleGenerationError(
                    "article_id is required when use_text is false"
                )
            return await self.regenerate_images(request.article_id)

        article = await self._repository.create(
            topic=request.topic,
            language=request.language,
            audience=request.audience,
            keywords=request.keywords_for_storage(),
            status=ArticleStatus.PENDING,
        )
        await self._repository.update(article.id, status=ArticleStatus.PROCESSING)
        logger.info(
            "Generating article id=%s language=%s topic=%s",
            article.id,
            request.language,
            request.topic,
        )
        run_id = await self._runs.start(
            "article", _article_run_input(request, article.id)
        )
        history_output: dict[str, object] | None = None
        try:
            assets, links, output, trace = await self._write_article(
                request, article, run_id
            )
            quality_result = await self._tracked_quality(run_id, request, output)
            if quality_result is not None:
                output = quality_result.output
            dzen_result = await self._tracked_dzen(run_id, request, output)
            completed = await self._tracked_save(
                run_id,
                article,
                request,
                output,
                trace,
                assets,
                links,
                dzen_result,
                quality_result,
            )
            history_output = {
                "article_id": str(completed.id),
                "title": completed.title or "",
                "url_slug": completed.url_slug or "",
                "word_count": completed.word_count,
                "images": _completed_images(assets),
                "images_failed": _counted_images(assets, "failed"),
                "links": len(links),
                "dzen": dzen_result.article.status if dzen_result is not None else None,
                **_quality_scores(quality_result),
            }
            return completed
        except Exception:
            raise
        except BaseException:
            await self._mark_interrupted(article.id)
            raise
        finally:
            await self._runs.finish_current(run_id, output_json=history_output)

    async def resolve_media(self, article_id: uuid.UUID, relative: str) -> Path | None:
        """Safe path to an image under this article's output folder."""
        article = await self._repository.get_by_id(article_id)
        if article is None:
            raise ArticleNotFoundError(article_id)
        return resolve_article_media_path(self._output_dir, article, relative)

    async def regenerate_images(self, article_id: uuid.UUID) -> Article:
        """Replace image slots on an existing article. Does not call the writer."""
        article = await self._repository.get_by_id(article_id)
        if article is None:
            raise ArticleNotFoundError(article_id)
        markdown = article.content_markdown or ""
        if not markdown.strip():
            raise ArticleGenerationError(
                "Article has no markdown to illustrate",
                article_id=article_id,
            )
        if self._image_service is None:
            raise ArticleGenerationError(
                _GENERIC_FAILURE_MESSAGE,
                article_id=article_id,
            )

        run_id = await self._runs.start("images", {"article_id": str(article.id)})
        history_output: dict[str, object] | None = None
        try:
            logger.info("Regenerating images for article id=%s", article.id)
            async with self._runs.step(run_id, "images") as handle:
                updated, assets = await self._image_service.replace_placeholders(
                    markdown,
                    topic=article.topic,
                    title=article.title or article.topic,
                    ensure_hero=True,
                )
                handle.detail = _image_detail(assets)
            dzen_payload = article.dzen if isinstance(article.dzen, dict) else None
            dzen_assets: list[GeneratedAsset] = []
            if dzen_payload:
                dzen_body = str(dzen_payload.get("content_markdown") or "")
                if dzen_body.strip():
                    async with self._runs.step(run_id, "dzen") as handle:
                        (
                            dzen_md,
                            dzen_assets,
                        ) = await self._image_service.replace_placeholders(
                            dzen_body,
                            topic=article.topic,
                            kinds={"cover", "dzen"},
                        )
                        dzen_payload = {
                            **dzen_payload,
                            "content_markdown": dzen_md,
                            "assets": [
                                item.model_dump(mode="json") for item in dzen_assets
                            ],
                        }
                        handle.detail = _image_detail(dzen_assets)
            async with self._runs.step(run_id, "save") as handle:
                completed = await self._repository.update(
                    article.id,
                    content_markdown=updated,
                    assets=[item.model_dump(mode="json") for item in assets] or None,
                    dzen=dzen_payload,
                    status=ArticleStatus.COMPLETED,
                    error_message=None,
                )
                if completed is None:
                    raise ArticleGenerationError(
                        _GENERIC_FAILURE_MESSAGE,
                        article_id=article_id,
                    )
                image_files = [
                    (item.path, item.data)
                    for item in [*assets, *dzen_assets]
                    if item.data and item.status == "completed"
                ]
                try_save_article_to_file(
                    completed, self._output_dir, image_files=image_files or None
                )
                handle.detail = {
                    "files": len(image_files),
                    "images": _completed_images(assets),
                    "dzen_images": _completed_images(dzen_assets),
                }
            logger.info(
                "Images refreshed id=%s files=%s", completed.id, len(image_files)
            )
            history_output = {
                "article_id": str(completed.id),
                "images": _completed_images(assets),
                "dzen_images": _completed_images(dzen_assets),
            }
            return completed
        finally:
            await self._runs.finish_current(run_id, output_json=history_output)

    async def _attach_competitor_research(
        self, request: ArticleWriteInput
    ) -> ArticleWriteInput:
        if self._research_service is None:
            return request
        return await self._research_service.attach_to_write_input(request)

    async def _research_file_payload(
        self, research_id: uuid.UUID | None
    ) -> dict[str, object] | None:
        if research_id is None or self._research_service is None:
            return None
        try:
            run = await self._research_service.get(research_id)
        except ResearchNotFoundError:
            return None
        return research_response(run, list(run.competitors)).model_dump(mode="json")

    async def _attach_knowledge_context(
        self, request: ArticleWriteInput
    ) -> ArticleWriteInput:
        if self._rag_service is None:
            return request
        context = await self._rag_service.context_for_article(request)
        if not context:
            return request
        return request.model_copy(update={"knowledge_context": context})

    async def _write_article(
        self,
        request: ArticleWriteInput,
        article: Article,
        run_id: uuid.UUID | None,
    ) -> tuple[
        list[GeneratedAsset],
        list[InternalLinkRef],
        AIArticleOutput,
        PipelineTrace | None,
    ]:
        """Research, write, images, and links. Failures mark the article failed."""
        assets: list[GeneratedAsset] = []
        links: list[InternalLinkRef] = []
        try:
            if request.use_multi_agent:
                output, trace = await self._run_multi_agent(request, run_id)
            else:
                async with self._runs.step(run_id, "research") as handle:
                    request = await self._attach_competitor_research(request)
                    if request.research_id is None:
                        handle.skip()
                    else:
                        handle.detail = {"research_id": str(request.research_id)}
                async with self._runs.step(run_id, "knowledge") as handle:
                    request = await self._attach_knowledge_context(request)
                    attached = bool(request.knowledge_context.strip())
                    handle.detail = {"attached": attached}
                    if not attached:
                        handle.skip()
                async with self._runs.step(run_id, "writer") as handle:
                    output = await self._writer.generate(request)
                    handle.detail = _draft_detail(output)
                trace = None
            markdown = output.content_markdown
            async with self._runs.step(run_id, "images") as handle:
                if request.use_images and self._image_service is not None:
                    markdown, assets = await self._image_service.replace_placeholders(
                        markdown,
                        topic=request.topic,
                        title=output.title,
                        ensure_hero=True,
                    )
                    handle.detail = _image_detail(assets)
                else:
                    handle.skip()
            async with self._runs.step(run_id, "links") as handle:
                if request.use_internal_links and self._linking_service is not None:
                    markdown, links = await self._linking_service.insert_links(
                        markdown,
                        article_id=article.id,
                        language=request.language,
                        keywords=request.keywords_for_storage(),
                        topic=request.topic,
                    )
                    handle.detail = {
                        "count": len(links),
                        "links": [
                            {"title": item.title, "slug": item.url_slug}
                            for item in links
                        ],
                    }
                else:
                    handle.skip()
            if markdown != output.content_markdown:
                output = output.model_copy(update={"content_markdown": markdown})
        except (AIConfigurationError, ResearchConfigurationError) as exc:
            logger.exception("AI provider is not configured")
            await self._mark_failed(article.id, _GENERIC_FAILURE_MESSAGE)
            raise ArticleGenerationError(
                _GENERIC_FAILURE_MESSAGE,
                article_id=article.id,
            ) from exc
        except (AIError, ResearchUpstreamError) as exc:
            await self._mark_failed(article.id, exc.message)
            raise ArticleGenerationUpstreamError(
                exc.message,
                article_id=article.id,
            ) from exc
        except (ResearchNotFoundError, ResearchError) as exc:
            await self._mark_failed(article.id, exc.message)
            raise ArticleGenerationError(
                exc.message,
                article_id=article.id,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error while generating article")
            await self._mark_failed(article.id, _GENERIC_FAILURE_MESSAGE)
            raise ArticleGenerationError(
                _GENERIC_FAILURE_MESSAGE,
                article_id=article.id,
            ) from exc
        return assets, links, output, trace

    async def _tracked_quality(
        self,
        run_id: uuid.UUID | None,
        request: ArticleWriteInput,
        output: AIArticleOutput,
    ) -> QualityRunResult | None:
        async with self._runs.step(run_id, "quality") as handle:
            result = await self._maybe_quality(request, output)
            if result is None:
                handle.skip()
            else:
                handle.detail = _quality_detail(result.report)
            return result

    async def _tracked_dzen(
        self,
        run_id: uuid.UUID | None,
        request: ArticleWriteInput,
        output: AIArticleOutput,
    ) -> DzenWriteResult | None:
        async with self._runs.step(run_id, "dzen") as handle:
            result = await self._maybe_dzen(request, output)
            if result is None or result.article.status in {"skipped", "failed"}:
                failed = result is not None and result.article.status == "failed"
                handle.status = "failed" if failed else "skipped"
            if result is not None:
                handle.detail = {
                    "status": result.article.status,
                    "chars": result.article.char_count,
                    "images": _completed_images(result.assets),
                }
            return result

    async def _tracked_save(
        self,
        run_id: uuid.UUID | None,
        article: Article,
        request: ArticleWriteInput,
        output: AIArticleOutput,
        trace: PipelineTrace | None,
        assets: list[GeneratedAsset],
        links: list[InternalLinkRef],
        dzen_result: DzenWriteResult | None,
        quality_result: QualityRunResult | None,
    ) -> Article:
        async with self._runs.step(run_id, "save") as handle:
            completed = await self._repository.update(
                article.id,
                title=output.title,
                meta_description=output.meta_description,
                url_slug=normalize_url_slug(output.url_slug, article_id=article.id),
                content_markdown=output.content_markdown,
                word_count=count_words(output.content_markdown),
                status=ArticleStatus.COMPLETED,
                error_message=None,
                pipeline=trace.model_dump(mode="json") if trace is not None else None,
                assets=(
                    [item.model_dump(mode="json") for item in assets]
                    if request.use_images
                    else None
                ),
                internal_links=(
                    [item.model_dump(mode="json") for item in links]
                    if request.use_internal_links
                    else None
                ),
                dzen=(
                    dzen_result.article.model_dump(mode="json")
                    if dzen_result is not None
                    else None
                ),
                quality=(
                    quality_result.report.model_dump(mode="json")
                    if quality_result is not None
                    else None
                ),
                competitor_sources=(
                    [
                        item.model_dump(mode="json")
                        for item in request.competitor_sources
                    ]
                    if request.competitor_sources
                    else None
                ),
            )
            if completed is None:
                raise ArticleGenerationError(
                    _GENERIC_FAILURE_MESSAGE,
                    article_id=article.id,
                )
            image_files = [
                (item.path, item.data)
                for item in assets
                if item.data and item.status == "completed"
            ]
            if dzen_result is not None:
                image_files.extend(
                    (item.path, item.data)
                    for item in dzen_result.assets
                    if item.data and item.status == "completed"
                )
            try_save_article_to_file(
                completed,
                self._output_dir,
                image_files=image_files or None,
                outline=request.outline,
                research_payload=await self._research_file_payload(request.research_id),
            )
            handle.detail = {
                "title": completed.title or "",
                "slug": completed.url_slug or "",
                "words": completed.word_count,
                "files": len(image_files),
            }
        logger.info(
            "Article completed id=%s words=%s slug=%s",
            completed.id,
            completed.word_count,
            completed.url_slug,
        )
        return completed

    async def _run_multi_agent(
        self,
        request: ArticleWriteInput,
        run_id: uuid.UUID | None,
    ) -> tuple[AIArticleOutput, PipelineTrace]:
        if self._pipeline_service is None:
            raise AIConfigurationError("Multi-agent pipeline is not configured")
        return await self._pipeline_service.run(request, run_id=run_id)

    async def _maybe_dzen(
        self, request: ArticleWriteInput, output: AIArticleOutput
    ) -> DzenWriteResult | None:
        if not request.use_dzen:
            return None
        if self._dzen_service is None:
            return DzenWriteResult(article=DzenArticle(status="skipped"))
        try:
            return await self._dzen_service.write(
                source_title=output.title,
                source_markdown=output.content_markdown,
                language=request.language,
                audience=request.audience,
                use_images=request.use_images,
            )
        except Exception:
            logger.exception("Dzen version failed; main article is unchanged")
            return DzenWriteResult(article=DzenArticle(status="failed"))

    async def _maybe_quality(
        self, request: ArticleWriteInput, output: AIArticleOutput
    ) -> QualityRunResult | None:
        wanted = request.use_detectors or request.use_humanizer or request.use_summary
        if not wanted:
            return None
        if self._quality_service is None:
            return None
        try:
            return await self._quality_service.run(
                output,
                language=request.language,
                audience=request.audience,
                use_detectors=request.use_detectors,
                use_humanizer=request.use_humanizer,
                use_summary=request.use_summary,
            )
        except Exception:
            logger.exception("Quality checks failed; main article is unchanged")
            return None

    async def _mark_interrupted(self, article_id: uuid.UUID) -> None:
        current = await self._repository.get_by_id(article_id)
        if current is None or current.status not in {
            ArticleStatus.PENDING,
            ArticleStatus.PROCESSING,
        }:
            return
        await self._mark_failed(article_id, INTERRUPTED_MESSAGE)

    async def _mark_failed(self, article_id: uuid.UUID, message: str) -> None:
        try:
            await self._repository.update(
                article_id,
                status=ArticleStatus.FAILED,
                error_message=message,
            )
        except Exception:
            # Never mask the original failure with a bookkeeping error.
            logger.exception("Could not mark article %s as failed", article_id)


def _article_run_input(
    request: ArticleWriteInput, article_id: uuid.UUID
) -> dict[str, object]:
    return {
        "topic": request.topic,
        "language": request.language,
        "article_id": str(article_id),
        "audience": request.audience,
        "keywords": request.keywords_for_storage(),
        "use_multi_agent": request.use_multi_agent,
        "use_competitor_research": request.use_competitor_research,
        "use_images": request.use_images,
        "use_internal_links": request.use_internal_links,
        "use_dzen": request.use_dzen,
        "use_detectors": request.use_detectors,
        "use_humanizer": request.use_humanizer,
        "use_summary": request.use_summary,
    }


def _completed_images(assets: list[GeneratedAsset]) -> int:
    return _counted_images(assets, "completed")


def _counted_images(assets: list[GeneratedAsset], status: str) -> int:
    return sum(1 for item in assets if item.status == status)


def _image_detail(assets: list[GeneratedAsset]) -> dict[str, object]:
    return {
        "completed": _counted_images(assets, "completed"),
        "failed": _counted_images(assets, "failed"),
        "slots": [
            {
                "kind": item.kind,
                "placeholder": item.placeholder,
                "path": item.path,
                "status": item.status,
            }
            for item in assets
        ],
    }


def _draft_detail(output: AIArticleOutput) -> dict[str, object]:
    return {
        "title": output.title,
        "slug": output.url_slug,
        "words": count_words(output.content_markdown),
    }


def _quality_scores(result: QualityRunResult | None) -> dict[str, object]:
    if result is None or result.report.detectors is None:
        return {}
    detectors = result.report.detectors
    return {
        "ai_likelihood": detectors.ai_likelihood,
        "uniqueness": detectors.uniqueness,
        "detector_verdict": detectors.verdict,
    }


def _quality_detail(report: QualityReport) -> dict[str, object]:
    detail: dict[str, object] = {}
    if report.detectors is not None:
        detail["detector"] = report.detectors.status
        detail["ai_likelihood"] = report.detectors.ai_likelihood
        detail["uniqueness"] = report.detectors.uniqueness
        detail["verdict"] = report.detectors.verdict
    if report.humanizer is not None:
        detail["humanizer"] = report.humanizer.status
        detail["humanizer_applied"] = report.humanizer.applied
    if report.summary is not None:
        detail["summary_chars"] = report.summary.char_count
    return detail
