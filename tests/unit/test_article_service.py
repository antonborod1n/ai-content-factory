"""Unit tests for ArticleService using in-memory doubles."""

import uuid
from pathlib import Path
from typing import Any

import pytest

from app.core.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIValidationError,
    ArticleGenerationError,
    ArticleGenerationUpstreamError,
    ArticleNotFoundError,
)
from app.core.word_count import count_words
from app.db.models.article import Article, ArticleStatus, ReviewStatus
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.services.ai.mock_detector import MockAiDetector
from app.services.ai.mock_dzen import MockDzenWriter
from app.services.ai.mock_editor import MockEditor
from app.services.ai.mock_fact_checker import MockFactChecker, needs_revision_output
from app.services.ai.mock_humanizer import MockHumanizer
from app.services.ai.mock_image import MINIMAL_PNG, MockImageProvider
from app.services.ai.mock_seo_agent import MockSeoAgent
from app.services.ai.mock_summarizer import MockSummarizer
from app.services.ai.mock_writer import MockAIWriter
from app.services.article_service import ArticleService
from app.services.dzen_service import DzenService
from app.services.image_service import ImageService
from app.services.linking_service import LinkingService
from app.services.pipeline_service import PipelineService
from app.services.quality_service import QualityService


class FakeArticleRepository:
    """In-memory stand-in for ArticleRepository."""

    def __init__(self) -> None:
        self.articles: dict[uuid.UUID, Article] = {}
        self.status_history: list[ArticleStatus] = []

    async def list_link_targets(
        self,
        *,
        language: str,
        exclude_id: uuid.UUID,
        limit: int = 50,
    ) -> list[Article]:
        rows = [
            article
            for article in self.articles.values()
            if article.status is ArticleStatus.COMPLETED
            and article.id != exclude_id
            and article.language == language
            and article.url_slug
            and article.title
        ]
        return rows[:limit]

    async def create(self, **fields: Any) -> Article:
        article = Article(id=uuid.uuid4(), **fields)
        self.articles[article.id] = article
        self.status_history.append(article.status)
        return article

    async def get_by_id(self, article_id: uuid.UUID) -> Article | None:
        return self.articles.get(article_id)

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: ArticleStatus | None = None,
        review_status: ReviewStatus | None = None,
    ) -> list[Article]:
        rows = list(self.articles.values())
        if status is not None:
            rows = [item for item in rows if item.status is status]
        if review_status is not None:
            rows = [item for item in rows if item.review_status is review_status]
        return rows[offset : offset + limit]

    async def count(
        self,
        *,
        status: ArticleStatus | None = None,
        review_status: ReviewStatus | None = None,
    ) -> int:
        rows = list(self.articles.values())
        if status is not None:
            rows = [item for item in rows if item.status is status]
        if review_status is not None:
            rows = [item for item in rows if item.review_status is review_status]
        return len(rows)

    async def update(self, article_id: uuid.UUID, **fields: Any) -> Article | None:
        article = self.articles.get(article_id)
        if article is None:
            return None
        for key, value in fields.items():
            setattr(article, key, value)
        if "status" in fields:
            self.status_history.append(fields["status"])
        return article


def _service(
    repository: FakeArticleRepository,
    writer: object,
    *,
    output_dir: str = "",
) -> ArticleService:
    return ArticleService(repository, writer, output_dir=output_dir)


LEAKY_SECRET = "fake-password-must-not-leak"


class ExplodingWriter:
    """Writer that raises a non-AI error containing sensitive text."""

    async def generate(self, request: ArticleWriteInput) -> AIArticleOutput:
        raise RuntimeError(
            f"connection to postgresql://acf:{LEAKY_SECRET}@db failed"
        )


def _request(**overrides: Any) -> ArticleWriteInput:
    payload: dict[str, Any] = {
        "topic": "Как выбрать промышленный насос",
        "language": "ru",
        "audience": "Инженеры и закупщики",
        "keywords": ["промышленный насос"],
    }
    payload.update(overrides)
    return ArticleWriteInput(**payload)


@pytest.mark.asyncio
async def test_get_and_list_articles() -> None:
    repository = FakeArticleRepository()
    service = _service(repository, MockAIWriter())
    created = await service.generate(_request())

    fetched = await service.get(created.id)
    assert fetched.id == created.id

    items, total = await service.list()
    assert total == 1
    assert items[0].id == created.id

    completed, completed_total = await service.list(status=ArticleStatus.COMPLETED)
    assert completed_total == 1
    assert completed[0].id == created.id

    failed, failed_total = await service.list(status=ArticleStatus.FAILED)
    assert failed_total == 0
    assert failed == []


@pytest.mark.asyncio
async def test_set_review_updates_verdict() -> None:
    repository = FakeArticleRepository()
    service = _service(repository, MockAIWriter())
    created = await service.generate(_request())

    reviewed = await service.set_review(created.id, ReviewStatus.APPROVED)
    assert reviewed.review_status is ReviewStatus.APPROVED
    assert reviewed.content_markdown == created.content_markdown


async def test_get_missing_article_raises() -> None:
    service = _service(FakeArticleRepository(), MockAIWriter())
    missing_id = uuid.uuid4()
    with pytest.raises(ArticleNotFoundError) as exc_info:
        await service.get(missing_id)
    assert exc_info.value.article_id == missing_id


@pytest.mark.asyncio
async def test_generate_completes_and_persists_content() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter()
    service = _service(repository, writer)

    article = await service.generate(_request())

    assert article.status is ArticleStatus.COMPLETED
    assert article.title == "Mock: Как выбрать промышленный насос"
    assert article.meta_description
    assert article.content_markdown
    assert article.error_message is None
    assert article.word_count == count_words(article.content_markdown)


@pytest.mark.asyncio
async def test_generate_writes_markdown_file(tmp_path: Path) -> None:
    repository = FakeArticleRepository()
    service = _service(repository, MockAIWriter(), output_dir=tmp_path)

    article = await service.generate(_request())

    article_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(article_dirs) == 1
    assert str(article.id) in article_dirs[0].name
    files = list(article_dirs[0].glob("*.md"))
    html_files = list(article_dirs[0].glob("*.html"))
    assert len(files) == 1
    assert len(html_files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert article.title in text
    assert article.content_markdown in text
    html_text = html_files[0].read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_text
    assert article.title in html_text


@pytest.mark.asyncio
async def test_generate_follows_status_transitions() -> None:
    repository = FakeArticleRepository()
    service = _service(repository, MockAIWriter())

    await service.generate(_request())

    assert repository.status_history == [
        ArticleStatus.PENDING,
        ArticleStatus.PROCESSING,
        ArticleStatus.COMPLETED,
    ]


@pytest.mark.asyncio
async def test_generate_stores_request_parameters() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter()
    service = _service(repository, writer)

    request = _request(language="en", audience="Buyers", keywords=["pump", "guide"])
    article = await service.generate(request)

    assert article.language == "en"
    assert article.audience == "Buyers"
    assert article.keywords == ["pump", "guide"]
    assert len(writer.calls) == 1
    assert writer.calls[0].topic == request.topic
    assert writer.calls[0].keywords == ["pump", "guide"]


@pytest.mark.asyncio
async def test_generate_recalculates_word_count_and_ignores_ai_value() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter(
        output=AIArticleOutput(
            title="Title",
            meta_description="Meta",
            content_markdown="# Heading\n\nexactly four real words",
            word_count=9999,
        )
    )
    service = _service(repository, writer)

    article = await service.generate(_request())

    assert article.word_count == 5
    assert article.word_count != 9999


@pytest.mark.asyncio
async def test_generate_marks_failed_on_ai_provider_error() -> None:
    repository = FakeArticleRepository()
    service = _service(repository, MockAIWriter(fail_with=AIProviderError()))

    with pytest.raises(ArticleGenerationUpstreamError) as exc_info:
        await service.generate(_request())

    article = next(iter(repository.articles.values()))
    assert exc_info.value.article_id == article.id
    assert isinstance(exc_info.value.__cause__, AIProviderError)
    assert article.status is ArticleStatus.FAILED
    assert article.error_message == (
        "Article generation failed due to an AI provider error"
    )
    assert article.content_markdown is None
    assert article.word_count is None
    assert repository.status_history == [
        ArticleStatus.PENDING,
        ArticleStatus.PROCESSING,
        ArticleStatus.FAILED,
    ]


@pytest.mark.asyncio
async def test_generate_marks_failed_on_invalid_ai_output() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter(invalid_payload={"title": "Only title"})
    service = _service(repository, writer)

    with pytest.raises(ArticleGenerationUpstreamError) as exc_info:
        await service.generate(_request())

    article = next(iter(repository.articles.values()))
    assert isinstance(exc_info.value.__cause__, AIValidationError)
    assert article.status is ArticleStatus.FAILED
    assert article.error_message == "AI response failed validation"
    assert article.title is None


@pytest.mark.asyncio
async def test_generate_treats_misconfiguration_as_internal_error() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter(fail_with=AIConfigurationError())
    service = _service(repository, writer)

    with pytest.raises(ArticleGenerationError) as exc_info:
        await service.generate(_request())

    assert not isinstance(exc_info.value, ArticleGenerationUpstreamError)
    assert str(exc_info.value) == "Article generation failed"

    article = next(iter(repository.articles.values()))
    assert article.status is ArticleStatus.FAILED
    assert article.error_message == "Article generation failed"


@pytest.mark.asyncio
async def test_generate_wraps_unexpected_error_with_safe_message() -> None:
    repository = FakeArticleRepository()
    service = _service(repository, ExplodingWriter())

    with pytest.raises(ArticleGenerationError) as exc_info:
        await service.generate(_request())

    message = str(exc_info.value)
    assert message == "Article generation failed"
    assert LEAKY_SECRET not in message

    article = next(iter(repository.articles.values()))
    assert article.status is ArticleStatus.FAILED
    assert article.error_message == "Article generation failed"
    assert LEAKY_SECRET not in article.error_message


class _FakeRagService:
    def __init__(self, context: str) -> None:
        self.context = context
        self.calls: list[ArticleWriteInput] = []

    async def context_for_article(self, request: ArticleWriteInput) -> str:
        self.calls.append(request)
        if not request.use_knowledge_base:
            return ""
        return self.context


@pytest.mark.asyncio
async def test_generate_attaches_knowledge_context() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter()
    rag = _FakeRagService("### Источник 1: Спека\nРабочее давление 10 бар.")
    service = ArticleService(repository, writer, rag_service=rag, output_dir="")

    await service.generate(_request())

    assert len(rag.calls) == 1
    assert "10 бар" in writer.calls[0].knowledge_context


@pytest.mark.asyncio
async def test_generate_skips_rag_when_use_knowledge_base_is_false() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter()
    rag = _FakeRagService("should not appear")
    service = ArticleService(repository, writer, rag_service=rag, output_dir="")

    await service.generate(_request(use_knowledge_base=False))

    assert rag.calls[0].use_knowledge_base is False
    assert writer.calls[0].knowledge_context == ""


class _RecordingPipeline:
    def __init__(self) -> None:
        self.calls: list[ArticleWriteInput] = []

    async def run(
        self, request: ArticleWriteInput
    ) -> tuple[AIArticleOutput, object]:
        self.calls.append(request)
        raise AssertionError("pipeline should not run")


@pytest.mark.asyncio
async def test_generate_does_not_run_pipeline_by_default() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter()
    pipeline = _RecordingPipeline()
    service = ArticleService(
        repository, writer, pipeline_service=pipeline, output_dir=""
    )

    article = await service.generate(_request())

    assert pipeline.calls == []
    assert article.title == "Mock: Как выбрать промышленный насос"
    assert article.pipeline is None


@pytest.mark.asyncio
async def test_generate_multi_agent_persists_editor_output_and_trace() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter()
    pipeline = PipelineService(
        writer,
        MockSeoAgent(),
        MockFactChecker(),
        MockEditor(),
        enabled=True,
        default_word_count=3000,
    )
    service = ArticleService(
        repository, writer, pipeline_service=pipeline, output_dir=""
    )

    article = await service.generate(_request(use_multi_agent=True))

    assert article.status is ArticleStatus.COMPLETED
    assert article.title.startswith("Edited: ")
    assert article.pipeline is not None
    names = [step["name"] for step in article.pipeline["steps"]]
    assert names == ["research", "seo", "writer", "fact_checker", "editor"]
    assert article.pipeline["steps"][0]["status"] == "skipped"


@pytest.mark.asyncio
async def test_humanizer_applies_fact_check_without_a_second_rewrite() -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter()
    editor = MockEditor()
    humanizer = MockHumanizer()
    pipeline = PipelineService(
        writer,
        MockSeoAgent(),
        MockFactChecker(output=needs_revision_output()),
        editor,
        enabled=True,
        default_word_count=3000,
    )
    service = ArticleService(
        repository,
        writer,
        pipeline_service=pipeline,
        quality_service=_quality_service(humanizer=humanizer),
        output_dir="",
    )

    article = await service.generate(
        _request(use_multi_agent=True, use_humanizer=True, use_internal_links=False)
    )

    assert editor.calls == []
    assert "Неподтверждённая цифра" in humanizer.calls[0].fact_check_notes
    assert "Текст звучит естественнее" in (article.content_markdown or "")
    assert article.pipeline is not None
    assert article.pipeline["steps"][-1]["status"] == "skipped"
    assert "editor_handoff" not in article.pipeline


@pytest.mark.asyncio
async def test_generate_multi_agent_without_pipeline_is_internal_error() -> None:
    repository = FakeArticleRepository()
    service = ArticleService(repository, MockAIWriter(), output_dir="")

    with pytest.raises(ArticleGenerationError) as exc_info:
        await service.generate(_request(use_multi_agent=True))

    assert not isinstance(exc_info.value, ArticleGenerationUpstreamError)
    article = next(iter(repository.articles.values()))
    assert article.status is ArticleStatus.FAILED


@pytest.mark.asyncio
async def test_generate_replaces_images_and_writes_file(tmp_path: Path) -> None:
    repository = FakeArticleRepository()
    writer = MockAIWriter(
        output=AIArticleOutput(
            title="Матрас",
            meta_description="Meta",
            url_slug="matras",
            content_markdown="# T\n\n![Кадр](IMAGE_PLACEHOLDER_1)\n",
            word_count=2,
        )
    )
    service = ArticleService(
        repository,
        writer,
        image_service=ImageService(MockImageProvider(), enabled=True),
        output_dir=tmp_path,
    )

    article = await service.generate(
        _request(use_images=True, use_internal_links=False)
    )

    assert "images/cover.png" in (article.content_markdown or "")
    assert "images/image-1.png" in (article.content_markdown or "")
    assert {item["kind"] for item in article.assets} == {"hero", "image"}
    assert all(item["status"] == "completed" for item in article.assets)
    assert "data" not in article.assets[0]
    article_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    pngs = list(article_dirs[0].glob("images/*.png"))
    assert {item.name for item in pngs} == {"cover.png", "image-1.png"}
    assert all(item.read_bytes() == MINIMAL_PNG for item in pngs)


@pytest.mark.asyncio
async def test_generate_images_only_skips_writer(tmp_path: Path) -> None:
    repository = FakeArticleRepository()
    existing = await repository.create(
        topic="Матрас",
        language="ru",
        audience="general",
        keywords=[],
        status=ArticleStatus.COMPLETED,
        title="Матрас",
        meta_description="Meta",
        content_markdown="# T\n\n![Кадр](images/image-1.png)\n",
        word_count=2,
    )
    writer = MockAIWriter()
    service = ArticleService(
        repository,
        writer,
        image_service=ImageService(MockImageProvider(), enabled=True),
        output_dir=tmp_path,
    )

    article = await service.generate(
        _request(
            use_text=False,
            use_images=True,
            article_id=existing.id,
            use_internal_links=False,
        )
    )

    assert writer.calls == []
    assert article.id == existing.id
    assert article.title == "Матрас"
    assert article.assets[0]["status"] == "completed"
    article_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert list(article_dirs[0].glob("images/*.png"))


@pytest.mark.asyncio
async def test_generate_inserts_internal_links_from_catalog() -> None:
    repository = FakeArticleRepository()
    linking = LinkingService(repository, enabled=True, max_links=5, href_prefix="/")
    first_writer = MockAIWriter(
        output=AIArticleOutput(
            title="Как выбрать жесткость матраса",
            meta_description="Meta",
            url_slug="kak-vybrat-zhestkost",
            content_markdown="# Как выбрать жесткость матраса\n\nБазовый гид.",
            word_count=5,
        )
    )
    first_service = ArticleService(
        repository, first_writer, linking_service=linking, output_dir=""
    )
    await first_service.generate(
        _request(
            topic="Как выбрать жесткость матраса",
            keywords=["жесткость матраса"],
            use_internal_links=False,
        )
    )

    second_writer = MockAIWriter(
        output=AIArticleOutput(
            title="Вес и поза сна",
            meta_description="Meta",
            url_slug="ves-i-poza",
            content_markdown=(
                "# Вес\n\nПри выборе смотрите на жесткость матраса и вес."
            ),
            word_count=8,
        )
    )
    second_service = ArticleService(
        repository, second_writer, linking_service=linking, output_dir=""
    )
    article = await second_service.generate(
        _request(topic="Вес и поза сна", keywords=["жесткость матраса"])
    )

    assert "/kak-vybrat-zhestkost" in (article.content_markdown or "")
    assert article.internal_links[0]["url_slug"] == "kak-vybrat-zhestkost"


@pytest.mark.asyncio
async def test_generate_writes_dzen_version(tmp_path: Path) -> None:
    repository = FakeArticleRepository()
    service = ArticleService(
        repository,
        MockAIWriter(),
        dzen_service=DzenService(
            MockDzenWriter(),
            image_service=ImageService(MockImageProvider(), enabled=True),
            enabled=True,
        ),
        output_dir=tmp_path,
    )
    article = await service.generate(
        _request(use_dzen=True, use_images=True, use_internal_links=False)
    )

    assert article.dzen["status"] == "completed"
    assert article.dzen["title"].startswith("Mock:")
    assert "images/dzen-cover.png" in article.dzen["content_markdown"]
    assert "images/dzen-1.png" in article.dzen["content_markdown"]
    assert "images/dzen-2.png" in article.dzen["content_markdown"]
    article_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert (article_dirs[0] / "dzen.md").is_file()
    assert (article_dirs[0] / "dzen.html").is_file()
    assert (article_dirs[0] / "images" / "dzen-cover.png").is_file()


def _quality_service(
    *,
    detector: MockAiDetector | None = None,
    humanizer: MockHumanizer | None = None,
    summarizer: MockSummarizer | None = None,
) -> QualityService:
    return QualityService(
        detector or MockAiDetector(),
        humanizer or MockHumanizer(),
        summarizer or MockSummarizer(),
        enabled=True,
        ai_review_threshold=70,
        uniqueness_floor=50,
        summary_target_char_count=500,
    )


@pytest.mark.asyncio
async def test_generate_humanizer_rewrites_body(tmp_path: Path) -> None:
    repository = FakeArticleRepository()
    service = ArticleService(
        repository,
        MockAIWriter(),
        quality_service=_quality_service(),
        output_dir=tmp_path,
    )
    article = await service.generate(
        _request(
            use_detectors=True,
            use_humanizer=True,
            use_summary=True,
            use_internal_links=False,
        )
    )

    assert article.status is ArticleStatus.COMPLETED
    assert "Текст звучит естественнее" in (article.content_markdown or "")
    assert article.quality["detectors"]["verdict"] == "pass"
    assert article.quality["humanizer"]["applied"] is True
    assert article.quality["summary"]["text"].startswith("Кратко:")
    article_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert (article_dirs[0] / "summary.md").is_file()
    md = (article_dirs[0] / "article.md").read_text(encoding="utf-8")
    assert "summary:" in md


@pytest.mark.asyncio
async def test_generate_dzen_uses_humanized_body() -> None:
    repository = FakeArticleRepository()
    dzen_writer = MockDzenWriter()
    service = ArticleService(
        repository,
        MockAIWriter(),
        quality_service=_quality_service(),
        dzen_service=DzenService(dzen_writer, enabled=True),
        output_dir="",
    )
    article = await service.generate(
        _request(
            use_humanizer=True,
            use_dzen=True,
            use_internal_links=False,
        )
    )
    assert "Текст звучит естественнее" in (article.content_markdown or "")
    assert "Текст звучит естественнее" in dzen_writer.calls[0].source_markdown


@pytest.mark.asyncio
async def test_generate_quality_failure_does_not_fail_article() -> None:
    class BoomQuality:
        async def run(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("quality exploded")

    repository = FakeArticleRepository()
    service = ArticleService(
        repository,
        MockAIWriter(),
        quality_service=BoomQuality(),  # type: ignore[arg-type]
        output_dir="",
    )
    article = await service.generate(
        _request(use_detectors=True, use_internal_links=False)
    )
    assert article.status is ArticleStatus.COMPLETED
    assert article.quality is None
    assert article.content_markdown


@pytest.mark.asyncio
async def test_generate_writes_competitor_urls_to_markdown(tmp_path: Path) -> None:
    from app.services.ai.mock_analyst import MockCompetitorAnalyst
    from app.services.research.mock_page_fetcher import MockPageFetcher
    from app.services.research.mock_searcher import MockSearchProvider
    from app.services.research_service import ResearchService
    from tests.unit.test_research_service import FakeResearchRepository

    repository = FakeArticleRepository()
    research = ResearchService(
        FakeResearchRepository(),
        MockSearchProvider(),
        MockPageFetcher(),
        MockCompetitorAnalyst(),
        enabled=True,
        top_n=3,
        default_word_count=3000,
    )
    service = ArticleService(
        repository,
        MockAIWriter(),
        research_service=research,
        output_dir=tmp_path,
    )
    article = await service.generate(
        _request(use_competitor_research=True, use_internal_links=False)
    )

    assert article.competitor_sources
    urls = [item["url"] for item in article.competitor_sources]
    assert "https://example.com/firm-mattress" in urls
    assert "https://example.com/firm-mattress" not in (article.content_markdown or "")
    article_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    md = (article_dirs[0] / "article.md").read_text(encoding="utf-8")
    assert "## Проанализированные конкуренты" in md
    assert "https://example.com/firm-mattress" in md
    html = (article_dirs[0] / "article.html").read_text(encoding="utf-8")
    assert "https://example.com/firm-mattress" not in html
    links = (article_dirs[0] / "competitors.txt").read_text(encoding="utf-8")
    assert "https://example.com/firm-mattress" in links.splitlines()
    research = (article_dirs[0] / "research.md").read_text(encoding="utf-8")
    assert "https://example.com/firm-mattress" in research
    generate = (article_dirs[0] / "stage3_generate.json").read_text(encoding="utf-8")
    assert str(article.id) in generate
    research_json = (article_dirs[0] / "stage3_research.json").read_text(
        encoding="utf-8"
    )
    assert "https://example.com/firm-mattress" in research_json

