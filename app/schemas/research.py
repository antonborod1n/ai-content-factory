"""Schemas for Stage 3 competitor research."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.research import ResearchStatus
from app.schemas.ai import CompetitorPlanOutput, SectionImageCount


class SearchHit(BaseModel):
    """One organic search result (no page body)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    snippet: str = ""
    rank: int = Field(ge=1)


class CompetitorProfile(BaseModel):
    """SERP hit plus extracted page structure."""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    title: str
    url: str
    snippet: str = ""
    headings: list[str] = Field(default_factory=list)
    section_images: list[SectionImageCount] = Field(default_factory=list)
    word_count: int = 0
    image_count: int = 0
    infographic_count: int = 0
    video_count: int = 0
    list_count: int = 0
    table_count: int = 0
    has_faq: bool = False
    features: list[str] = Field(default_factory=list)
    fetch_status: str = "pending"


class CompetitorPlanInput(BaseModel):
    """Input for CompetitorAnalyst (AI layer)."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    language: str = "ru"
    audience: str = "general"
    keywords: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=1)
    competitors: list[CompetitorProfile] = Field(default_factory=list)


class ResearchRequest(BaseModel):
    """Body of POST /api/v1/research."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    language: str = Field(default="ru", min_length=1)
    audience: str = Field(default="general", min_length=1)
    keywords: list[str] = Field(default_factory=list)
    word_count: int | None = Field(default=None, ge=1)
    top_n: int | None = Field(default=None, ge=1, le=10)

    @field_validator("topic", "language", "audience")
    @classmethod
    def _require_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("keywords")
    @classmethod
    def _clean_keywords(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class CompetitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rank: int
    title: str
    url: str
    snippet: str
    headings: list[str]
    section_images: list[SectionImageCount] = Field(default_factory=list)
    word_count: int
    image_count: int
    video_count: int
    list_count: int
    table_count: int
    has_faq: bool
    features: list[str]
    fetch_status: str


class ResearchResponse(BaseModel):
    """Stored competitor research run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic: str
    language: str
    audience: str
    query: str
    status: ResearchStatus
    outline: list[str]
    section_image_placeholders: list[int] = Field(default_factory=list)
    title_hint: str
    meta_description_hint: str
    url_slug_hint: str
    article_goal: str
    notes: str
    competitors: list[CompetitorResponse] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ResearchListResponse(BaseModel):
    items: list[ResearchResponse]
    total: int


class ResearchErrorResponse(BaseModel):
    """Sanitized research failure. Never contains secrets."""

    detail: str
    id: uuid.UUID | None = None
    status: ResearchStatus | None = None


def competitor_response(row: object) -> CompetitorResponse:
    return CompetitorResponse.model_validate(row)


def research_response(run: object, competitors: list[object]) -> ResearchResponse:
    payload = ResearchResponse.model_validate(run)
    payload.competitors = [competitor_response(item) for item in competitors]
    return payload


def format_competitor_context(
    plan: CompetitorPlanOutput,
    profiles: list[CompetitorProfile],
) -> str:
    """Prompt block: SEO hints plus competitor outlines. No full page text."""
    lines: list[str] = []
    if plan.title_hint.strip():
        lines.append(f"Подсказка title: {plan.title_hint.strip()}")
    if plan.meta_description_hint.strip():
        lines.append(
            f"Подсказка meta description: {plan.meta_description_hint.strip()}"
        )
    if plan.url_slug_hint.strip():
        lines.append(f"Подсказка url_slug: {plan.url_slug_hint.strip()}")
    if plan.notes.strip():
        lines.append(f"Заметки по выдаче: {plan.notes.strip()}")
    if plan.article_goal.strip():
        lines.append(f"Цель после анализа: {plan.article_goal.strip()}")

    for profile in profiles:
        heading_text = ", ".join(profile.headings[:12]) or "(заголовки не извлечены)"
        features = ", ".join(profile.features) or "нет"
        section_bits = [
            f"{item.heading}×{item.image_count}"
            for item in profile.section_images
            if item.heading and item.image_count
        ]
        section_text = (
            f" картинки по блокам: {'; '.join(section_bits)}."
            if section_bits
            else ""
        )
        lines.append(
            f"Конкурент {profile.rank}: {profile.title} ({profile.url}). "
            f"слов≈{profile.word_count}, картинок={profile.image_count}, "
            f"видео={profile.video_count}, фишки={features}.{section_text} "
            f"H2/H3: {heading_text}"
        )
    return "\n".join(lines)
