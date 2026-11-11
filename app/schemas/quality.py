"""Stage 6 quality DTOs: detectors, humanizer, summary."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ai import MODEL_OUTPUT_CONFIG, AIArticleOutput


class DetectorInput(BaseModel):
    """Draft sent to the AI/uniqueness detector."""

    model_config = ConfigDict(extra="forbid")

    title: str
    content_markdown: str
    language: str = "ru"


class DetectorSignal(BaseModel):
    model_config = MODEL_OUTPUT_CONFIG

    name: str
    detail: str = ""


class DetectorOutput(BaseModel):
    """Scores from the detector model (verdict is recalculated in the service)."""

    model_config = MODEL_OUTPUT_CONFIG

    ai_likelihood: int = Field(ge=0, le=100)
    uniqueness: int = Field(ge=0, le=100)
    notes: str = ""
    signals: list[DetectorSignal] = Field(default_factory=list)


class DetectorReport(BaseModel):
    """Persisted detector result. No article body."""

    model_config = ConfigDict(extra="forbid")

    status: str
    ai_likelihood: int = 0
    uniqueness: int = 0
    verdict: str = ""
    notes: str = ""
    signals: list[DetectorSignal] = Field(default_factory=list)


class HumanizerInput(BaseModel):
    """Draft sent to the humanizer."""

    model_config = ConfigDict(extra="forbid")

    title: str
    meta_description: str
    url_slug: str = ""
    content_markdown: str
    language: str = "ru"
    audience: str = "general"
    detector_notes: str = ""
    fact_check_notes: str = ""


class HumanizerReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    applied: bool = False


class SummaryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    content_markdown: str
    language: str = "ru"
    target_char_count: int = Field(default=500, ge=80)


class SummaryOutput(BaseModel):
    model_config = MODEL_OUTPUT_CONFIG

    summary: str = Field(min_length=1)


class SummaryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    text: str = ""
    char_count: int = 0


class QualityReport(BaseModel):
    """Compact quality payload stored on the article (no full draft)."""

    model_config = ConfigDict(extra="forbid")

    detectors: DetectorReport | None = None
    humanizer: HumanizerReport | None = None
    summary: SummaryReport | None = None


class QualityRunResult(BaseModel):
    """Runtime result: possibly rewritten article + persistable report."""

    model_config = ConfigDict(extra="forbid")

    output: AIArticleOutput
    report: QualityReport
