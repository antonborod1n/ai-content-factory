"""QualityService with mock detector / humanizer / summarizer."""

import pytest

from app.core.exceptions import AIConfigurationError, AIProviderError
from app.schemas.ai import AIArticleOutput
from app.schemas.quality import DetectorOutput
from app.services.ai.mock_detector import MockAiDetector
from app.services.ai.mock_humanizer import MockHumanizer
from app.services.ai.mock_summarizer import MockSummarizer
from app.services.quality_service import QualityService


def _output() -> AIArticleOutput:
    return AIArticleOutput(
        title="Как выбрать матрас",
        meta_description="Гид по жесткости",
        url_slug="kak-vybrat-matras",
        content_markdown="# Как выбрать матрас\n\nТекст статьи.\n",
        word_count=5,
    )


def _service(
    *,
    detector: MockAiDetector | None = None,
    humanizer: MockHumanizer | None = None,
    summarizer: MockSummarizer | None = None,
    enabled: bool = True,
) -> tuple[QualityService, MockAiDetector, MockHumanizer, MockSummarizer]:
    detector = detector or MockAiDetector()
    humanizer = humanizer or MockHumanizer()
    summarizer = summarizer or MockSummarizer()
    service = QualityService(
        detector,
        humanizer,
        summarizer,
        enabled=enabled,
        ai_review_threshold=70,
        uniqueness_floor=50,
        summary_target_char_count=500,
    )
    return service, detector, humanizer, summarizer


@pytest.mark.asyncio
async def test_detectors_use_backend_verdict() -> None:
    service, detector, _, _ = _service(
        detector=MockAiDetector(
            output=DetectorOutput(ai_likelihood=90, uniqueness=80, notes="шаблон")
        )
    )
    result = await service.run(
        _output(),
        language="ru",
        audience="general",
        use_detectors=True,
        use_humanizer=False,
        use_summary=False,
    )
    assert result.report.detectors is not None
    assert result.report.detectors.status == "completed"
    assert result.report.detectors.ai_likelihood == 90
    assert result.report.detectors.verdict == "review"
    assert result.report.humanizer is None
    assert result.report.summary is None
    assert detector.calls


@pytest.mark.asyncio
async def test_humanizer_rewrites_markdown() -> None:
    service, _, humanizer, _ = _service()
    original = _output()
    result = await service.run(
        original,
        language="ru",
        audience="покупатели",
        use_detectors=True,
        use_humanizer=True,
        use_summary=False,
    )
    assert result.report.humanizer is not None
    assert result.report.humanizer.status == "completed"
    assert result.report.humanizer.applied is True
    assert "Текст звучит естественнее" in result.output.content_markdown
    assert "стиль в порядке" in humanizer.calls[0].detector_notes


@pytest.mark.asyncio
async def test_summary_uses_humanized_draft() -> None:
    service, _, _, summarizer = _service()
    result = await service.run(
        _output(),
        language="ru",
        audience="general",
        use_detectors=False,
        use_humanizer=True,
        use_summary=True,
    )
    assert result.report.summary is not None
    assert result.report.summary.status == "completed"
    assert result.report.summary.text.startswith("Кратко:")
    assert result.report.summary.char_count == len(result.report.summary.text)
    assert "естественнее" in summarizer.calls[0].content_markdown


@pytest.mark.asyncio
async def test_disabled_skips_requested_steps() -> None:
    service, detector, humanizer, summarizer = _service(enabled=False)
    result = await service.run(
        _output(),
        language="ru",
        audience="general",
        use_detectors=True,
        use_humanizer=True,
        use_summary=True,
    )
    assert result.report.detectors is not None
    assert result.report.detectors.status == "skipped"
    assert result.report.humanizer is not None
    assert result.report.humanizer.status == "skipped"
    assert result.report.summary is not None
    assert result.report.summary.status == "skipped"
    assert detector.calls == []
    assert humanizer.calls == []
    assert summarizer.calls == []


@pytest.mark.asyncio
async def test_detector_error_does_not_raise() -> None:
    service, _, _, _ = _service(
        detector=MockAiDetector(fail_with=AIProviderError())
    )
    result = await service.run(
        _output(),
        language="ru",
        audience="general",
        use_detectors=True,
        use_humanizer=False,
        use_summary=False,
    )
    assert result.report.detectors is not None
    assert result.report.detectors.status == "failed"


@pytest.mark.asyncio
async def test_missing_config_skips_step() -> None:
    service, _, _, _ = _service(
        humanizer=MockHumanizer(fail_with=AIConfigurationError())
    )
    original = _output()
    result = await service.run(
        original,
        language="ru",
        audience="general",
        use_detectors=False,
        use_humanizer=True,
        use_summary=False,
    )
    assert result.report.humanizer is not None
    assert result.report.humanizer.status == "skipped"
    assert result.output.content_markdown == original.content_markdown
