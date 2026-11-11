"""Unit tests for PipelineService using in-memory doubles."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.core.exceptions import AIConfigurationError, ResearchConfigurationError
from app.schemas.ai import AIArticleOutput, ArticleWriteInput
from app.schemas.pipeline import (
    PipelineStepName,
    PipelineStepStatus,
    SeoPlanOutput,
)
from app.services.ai.mock_editor import MockEditor
from app.services.ai.mock_fact_checker import MockFactChecker, needs_revision_output
from app.services.ai.mock_seo_agent import MockSeoAgent
from app.services.ai.mock_writer import MockAIWriter
from app.services.pipeline_service import PipelineService


class FakeRagService:
    def __init__(self, context: str = "### Источник\nФакт из базы.") -> None:
        self.context = context
        self.calls: list[ArticleWriteInput] = []

    async def context_for_article(self, request: ArticleWriteInput) -> str:
        self.calls.append(request)
        if not request.use_knowledge_base:
            return ""
        return self.context


class FakeResearchService:
    def __init__(
        self,
        *,
        fail_config: bool = False,
        outline: list[str] | None = None,
    ) -> None:
        self.fail_config = fail_config
        self.outline = outline or ["Вес", "Поза", "FAQ"]
        self.calls: list[ArticleWriteInput] = []
        self.research_id = uuid.uuid4()

    async def attach_to_write_input(
        self, request: ArticleWriteInput
    ) -> ArticleWriteInput:
        self.calls.append(request)
        if self.fail_config:
            raise ResearchConfigurationError("Competitor research is disabled")
        return request.model_copy(
            update={
                "outline": list(self.outline),
                "competitor_context": "from research",
                "research_id": self.research_id,
            }
        )


def _request(**overrides: Any) -> ArticleWriteInput:
    payload: dict[str, Any] = {
        "topic": "Жесткость матраса",
        "use_multi_agent": True,
    }
    payload.update(overrides)
    return ArticleWriteInput(**payload)


def _pipeline(
    *,
    writer: MockAIWriter | None = None,
    seo: MockSeoAgent | None = None,
    fact: MockFactChecker | None = None,
    editor: MockEditor | None = None,
    rag: FakeRagService | None = None,
    research: FakeResearchService | None = None,
    enabled: bool = True,
) -> PipelineService:
    return PipelineService(
        writer or MockAIWriter(),
        seo or MockSeoAgent(),
        fact or MockFactChecker(),
        editor or MockEditor(),
        rag_service=rag if rag is not None else FakeRagService(),
        research_service=research,
        enabled=enabled,
        default_word_count=3000,
    )


@pytest.mark.asyncio
async def test_pipeline_runs_agents_in_order() -> None:
    writer = MockAIWriter()
    seo = MockSeoAgent()
    fact = MockFactChecker()
    editor = MockEditor()
    research = FakeResearchService()
    rag = FakeRagService()
    service = _pipeline(
        writer=writer, seo=seo, fact=fact, editor=editor, rag=rag, research=research
    )

    output, trace = await service.run(_request())

    assert [step.name for step in trace.steps] == [
        PipelineStepName.RESEARCH,
        PipelineStepName.SEO,
        PipelineStepName.WRITER,
        PipelineStepName.FACT_CHECKER,
        PipelineStepName.EDITOR,
    ]
    assert all(step.status is PipelineStepStatus.COMPLETED for step in trace.steps)
    assert research.calls
    assert seo.calls
    assert rag.calls
    assert writer.calls
    assert fact.calls
    assert editor.calls
    assert output.title.startswith("Edited: ")
    assert "Пояснение от редактора" in output.content_markdown


@pytest.mark.asyncio
async def test_writer_receives_seo_outline_and_rag_context() -> None:
    writer = MockAIWriter()
    seo = MockSeoAgent(
        output=SeoPlanOutput(
            outline=["Раздел A", "Раздел B", "FAQ"],
            primary_keywords=["жесткость матраса"],
            title_hint="Как выбрать жесткость",
            notes="усилил H2",
        )
    )
    research = FakeResearchService(outline=["Старый план", "Ещё"])
    rag = FakeRagService("### Спека\nПлотность 35.")
    service = _pipeline(writer=writer, seo=seo, rag=rag, research=research)

    await service.run(_request())

    used = writer.calls[0]
    assert used.outline == ["Раздел A", "Раздел B", "FAQ"]
    assert used.primary_keywords == ["жесткость матраса"]
    assert "Плотность 35" in used.knowledge_context
    assert "from research" in used.competitor_context
    assert "title_hint: Как выбрать жесткость" in used.competitor_context


@pytest.mark.asyncio
async def test_research_config_error_skips_research_step() -> None:
    writer = MockAIWriter()
    research = FakeResearchService(fail_config=True)
    service = _pipeline(writer=writer, research=research)

    _output, trace = await service.run(_request())

    assert trace.steps[0].name is PipelineStepName.RESEARCH
    assert trace.steps[0].status is PipelineStepStatus.SKIPPED
    assert writer.calls


@pytest.mark.asyncio
async def test_research_not_wired_is_skipped() -> None:
    service = _pipeline(research=None)
    _output, trace = await service.run(_request())
    assert trace.steps[0].status is PipelineStepStatus.SKIPPED
    assert trace.steps[0].notes == "research service not wired"


@pytest.mark.asyncio
async def test_fact_checker_sees_writer_draft_and_editor_sees_issues() -> None:
    writer = MockAIWriter(
        output=AIArticleOutput(
            title="Черновик",
            meta_description="Meta",
            content_markdown="# Черновик\n\nГарантия 100 лет.",
            word_count=4,
            url_slug="chernovik",
        )
    )
    fact = MockFactChecker(output=needs_revision_output())
    editor = MockEditor()
    service = _pipeline(writer=writer, fact=fact, editor=editor, research=None)

    output, trace = await service.run(_request())

    assert fact.calls[0].content_markdown.startswith("# Черновик")
    fact_step = trace.steps[3]
    assert fact_step.verdict == "needs_revision"
    assert fact_step.issue_count == 1
    assert editor.calls[0].fact_check.verdict == "needs_revision"
    assert output.title == "Edited: Черновик"


@pytest.mark.asyncio
async def test_disabled_pipeline_raises_configuration_error() -> None:
    service = _pipeline(enabled=False)
    with pytest.raises(AIConfigurationError, match="disabled"):
        await service.run(_request())
