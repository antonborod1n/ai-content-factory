"""Stage 4 multi-agent pipeline contracts (SEO / fact-check / editor / trace)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ai import MODEL_OUTPUT_CONFIG, AIArticleOutput


class PipelineStepName(StrEnum):
    RESEARCH = "research"
    SEO = "seo"
    WRITER = "writer"
    FACT_CHECKER = "fact_checker"
    EDITOR = "editor"


class PipelineStepStatus(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class PipelineStepTrace(BaseModel):
    """One agent step. Never stores article body, vectors, or secrets."""

    model_config = ConfigDict(extra="forbid")

    name: PipelineStepName
    status: PipelineStepStatus
    notes: str = ""
    issue_count: int | None = None
    verdict: str | None = None


class PipelineTrace(BaseModel):
    """Compact run log persisted on the article and returned by generate."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    steps: list[PipelineStepTrace] = Field(default_factory=list)
    # Fact-check text for the humanizer when the editor step is skipped.
    # Not stored on the article.
    editor_handoff: str = Field(default="", exclude=True)


class SeoPlanInput(BaseModel):
    """Brief + competitor notes for the SEO agent."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    language: str = "ru"
    audience: str = "general"
    keywords: list[str] = Field(default_factory=list)
    primary_keywords: list[str] = Field(default_factory=list)
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = "informational_commercial"
    article_goal: str = ""
    outline: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=1)
    competitor_context: str = ""


class SeoPlanOutput(BaseModel):
    """Refined outline and SEO wrapper hints (not page copy)."""

    model_config = MODEL_OUTPUT_CONFIG

    outline: list[str] = Field(min_length=2)
    primary_keywords: list[str] = Field(default_factory=list)
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = ""
    title_hint: str = ""
    meta_description_hint: str = ""
    url_slug_hint: str = ""
    article_goal: str = ""
    notes: str = ""


class FactCheckIssue(BaseModel):
    """One questionable claim. Keep text short; no full article dump."""

    model_config = MODEL_OUTPUT_CONFIG

    severity: str = Field(default="warning")
    claim: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    suggestion: str = ""


class FactCheckInput(BaseModel):
    """Draft + sources the fact checker may use."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    language: str = "ru"
    title: str
    meta_description: str
    content_markdown: str = Field(min_length=1)
    knowledge_context: str = ""
    competitor_context: str = ""


class FactCheckOutput(BaseModel):
    """Verdict after reviewing the writer draft."""

    model_config = MODEL_OUTPUT_CONFIG

    verdict: str = Field(default="ok")
    issues: list[FactCheckIssue] = Field(default_factory=list)
    notes: str = ""


class EditorInput(BaseModel):
    """Writer draft plus fact-check notes for the editor agent."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    language: str = "ru"
    audience: str = "general"
    outline: list[str] = Field(default_factory=list)
    knowledge_context: str = ""
    competitor_context: str = ""
    draft: AIArticleOutput
    fact_check: FactCheckOutput


def format_seo_context(plan: SeoPlanOutput) -> str:
    """Short SEO block merged into competitor_context for the writer."""
    keywords = ", ".join(plan.primary_keywords) or "(не заданы)"
    secondary = ", ".join(plan.secondary_keywords) or "(нет)"
    lines = [
        "SEO-агент (использовать для обёртки и акцентов, не копировать дословно):",
        f"- title_hint: {plan.title_hint or '(нет)'}",
        f"- meta_description_hint: {plan.meta_description_hint or '(нет)'}",
        f"- url_slug_hint: {plan.url_slug_hint or '(нет)'}",
        f"- search_intent: {plan.search_intent or '(нет)'}",
        f"- primary_keywords: {keywords}",
        f"- secondary_keywords: {secondary}",
    ]
    if plan.notes.strip():
        lines.append(f"- notes: {plan.notes.strip()}")
    return "\n".join(lines)
