"""Run detectors, optional humanizer, and summary. Failures skip that step."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.core.exceptions import AIConfigurationError, AIError
from app.core.quality import clamp_score, detector_verdict
from app.core.word_count import count_characters
from app.schemas.ai import AIArticleOutput
from app.schemas.quality import (
    DetectorInput,
    DetectorReport,
    HumanizerInput,
    HumanizerReport,
    QualityReport,
    QualityRunResult,
    SummaryInput,
    SummaryReport,
)
from app.services.ai.detector import AiDetector
from app.services.ai.humanizer import Humanizer
from app.services.ai.summarizer import Summarizer

logger = logging.getLogger(__name__)


class QualityService:
    """Orchestrates quality steps. No SQL, no SDK."""

    def __init__(
        self,
        detector: AiDetector,
        humanizer: Humanizer,
        summarizer: Summarizer,
        *,
        enabled: bool | None = None,
        ai_review_threshold: int | None = None,
        uniqueness_floor: int | None = None,
        summary_target_char_count: int | None = None,
    ) -> None:
        settings = get_settings()
        self._detector = detector
        self._humanizer = humanizer
        self._summarizer = summarizer
        self._enabled = settings.quality_enabled if enabled is None else enabled
        self._ai_review_threshold = (
            settings.detector_ai_review_threshold
            if ai_review_threshold is None
            else ai_review_threshold
        )
        self._uniqueness_floor = (
            settings.detector_uniqueness_floor
            if uniqueness_floor is None
            else uniqueness_floor
        )
        self._summary_target_char_count = (
            settings.summary_target_char_count
            if summary_target_char_count is None
            else summary_target_char_count
        )

    async def run(
        self,
        output: AIArticleOutput,
        *,
        language: str,
        audience: str,
        use_detectors: bool,
        use_humanizer: bool,
        use_summary: bool,
    ) -> QualityRunResult:
        report = QualityReport()
        current = output
        if not self._enabled:
            logger.info("Quality checks disabled; skipping")
            return QualityRunResult(
                output=current,
                report=_all_skipped(use_detectors, use_humanizer, use_summary),
            )

        detector_notes = ""
        if use_detectors:
            report.detectors = await self._scan(current, language=language)
            if report.detectors.status == "completed":
                detector_notes = report.detectors.notes

        if use_humanizer:
            current, report.humanizer = await self._humanize(
                current,
                language=language,
                audience=audience,
                detector_notes=detector_notes,
            )

        if use_summary:
            report.summary = await self._summarize(current, language=language)

        logger.info(
            "Quality finished detectors=%s humanizer=%s summary=%s",
            _status(report.detectors),
            _status(report.humanizer),
            _status(report.summary),
        )
        return QualityRunResult(output=current, report=report)

    async def _scan(
        self, output: AIArticleOutput, *, language: str
    ) -> DetectorReport:
        try:
            raw = await self._detector.scan(
                DetectorInput(
                    title=output.title,
                    content_markdown=output.content_markdown,
                    language=language,
                )
            )
        except AIConfigurationError:
            logger.info("Detector is not configured; skipping")
            return DetectorReport(status="skipped")
        except AIError:
            logger.warning("Detector failed; main article is unchanged")
            return DetectorReport(status="failed")
        except Exception:
            logger.exception("Unexpected error during detection")
            return DetectorReport(status="failed")

        ai_likelihood = clamp_score(raw.ai_likelihood)
        uniqueness = clamp_score(raw.uniqueness)
        return DetectorReport(
            status="completed",
            ai_likelihood=ai_likelihood,
            uniqueness=uniqueness,
            verdict=detector_verdict(
                ai_likelihood,
                uniqueness,
                ai_review_threshold=self._ai_review_threshold,
                uniqueness_floor=self._uniqueness_floor,
            ),
            notes=raw.notes,
            signals=list(raw.signals),
        )

    async def _humanize(
        self,
        output: AIArticleOutput,
        *,
        language: str,
        audience: str,
        detector_notes: str,
    ) -> tuple[AIArticleOutput, HumanizerReport]:
        try:
            rewritten = await self._humanizer.humanize(
                HumanizerInput(
                    title=output.title,
                    meta_description=output.meta_description,
                    url_slug=output.url_slug,
                    content_markdown=output.content_markdown,
                    language=language,
                    audience=audience,
                    detector_notes=detector_notes,
                )
            )
        except AIConfigurationError:
            logger.info("Humanizer is not configured; skipping")
            return output, HumanizerReport(status="skipped")
        except AIError:
            logger.warning("Humanizer failed; keeping original draft")
            return output, HumanizerReport(status="failed")
        except Exception:
            logger.exception("Unexpected error during humanizing")
            return output, HumanizerReport(status="failed")
        return rewritten, HumanizerReport(status="completed", applied=True)

    async def _summarize(
        self, output: AIArticleOutput, *, language: str
    ) -> SummaryReport:
        try:
            raw = await self._summarizer.summarize(
                SummaryInput(
                    title=output.title,
                    content_markdown=output.content_markdown,
                    language=language,
                    target_char_count=self._summary_target_char_count,
                )
            )
        except AIConfigurationError:
            logger.info("Summarizer is not configured; skipping")
            return SummaryReport(status="skipped")
        except AIError:
            logger.warning("Summarizer failed")
            return SummaryReport(status="failed")
        except Exception:
            logger.exception("Unexpected error during summarizing")
            return SummaryReport(status="failed")
        text = raw.summary.strip()
        return SummaryReport(
            status="completed",
            text=text,
            char_count=count_characters(text),
        )


def _status(item: DetectorReport | HumanizerReport | SummaryReport | None) -> str:
    return item.status if item is not None else "off"


def _all_skipped(
    use_detectors: bool, use_humanizer: bool, use_summary: bool
) -> QualityReport:
    return QualityReport(
        detectors=DetectorReport(status="skipped") if use_detectors else None,
        humanizer=HumanizerReport(status="skipped") if use_humanizer else None,
        summary=SummaryReport(status="skipped") if use_summary else None,
    )
