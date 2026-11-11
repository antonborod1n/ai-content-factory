"""Schemas for competitor-inventory content plans."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.competitor_plan import (
    DEFAULT_LANGUAGE,
    DEFAULT_TONE,
    CompetitorPlan,
    CompetitorPlanTopic,
)
from app.db.models.discovery import ContentPlanSource, ContentPlanStatus
from app.schemas.articles import ArticleGenerateRequest
from app.schemas.discovery import DiscoveryExportRequest, DiscoveryExportResponse


class CompetitorTopicsImportRequest(BaseModel):
    """Body of POST /api/v1/competitor-topics (raw content-plan JSON is valid)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    domain: str = ""
    niche: str = ""
    audience: str = ""
    geo: str = ""
    site_type: str = Field(default="", alias="siteType")
    blog_format: str = Field(default="", alias="blogFormat")
    topics: list[CompetitorPlanTopic] = Field(min_length=1)
    language: str = Field(default=DEFAULT_LANGUAGE, min_length=1)
    tone: str = DEFAULT_TONE
    use_knowledge_base: bool = True
    use_competitor_research: bool = True
    use_multi_agent: bool = False
    use_text: bool = True
    use_images: bool = False
    use_internal_links: bool = True
    use_dzen: bool = False
    use_detectors: bool = False
    use_humanizer: bool = False
    use_summary: bool = False

    @field_validator("language")
    @classmethod
    def _require_language(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("domain", "niche", "audience", "geo", "tone")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    def to_plan(self) -> CompetitorPlan:
        return CompetitorPlan(
            domain=self.domain,
            niche=self.niche,
            audience=self.audience or "general",
            geo=self.geo,
            site_type=self.site_type,
            blog_format=self.blog_format,
            topics=self.topics,
        )


class CompetitorTopicsSourcesRequest(BaseModel):
    """Form metadata for POST /competitor-topics/sources (raw dumps)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    domain: str = ""
    niche: str = ""
    audience: str = ""
    geo: str = ""
    site_type: str = Field(default="", alias="siteType")
    blog_format: str = Field(default="", alias="blogFormat")
    language: str = Field(default=DEFAULT_LANGUAGE, min_length=1)
    tone: str = DEFAULT_TONE
    use_knowledge_base: bool = True
    use_competitor_research: bool = True
    use_multi_agent: bool = False
    use_text: bool = True
    use_images: bool = False
    use_internal_links: bool = True
    use_dzen: bool = False
    use_detectors: bool = False
    use_humanizer: bool = False
    use_summary: bool = False

    @field_validator("language")
    @classmethod
    def _require_language(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("domain", "niche", "audience", "geo", "tone")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()


class ContentGapHit(BaseModel):
    """One extracted URL slug or keyword from a competitor dump."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    competitor: str = ""
    kind: str = "keyword"
    url: str = ""
    source_file: str = ""


class ContentGapInput(BaseModel):
    """Input for ContentGapAnalyst (AI layer)."""

    model_config = ConfigDict(extra="forbid")

    domain: str = ""
    niche: str = ""
    audience: str = ""
    geo: str = ""
    site_type: str = ""
    language: str = DEFAULT_LANGUAGE
    max_topics: int = Field(ge=1, le=300)
    hits: list[ContentGapHit] = Field(default_factory=list)


class ContentGapOutput(BaseModel):
    """Rewritten content-plan topics from competitor inventory hits."""

    model_config = ConfigDict(extra="ignore")

    topics: list[CompetitorPlanTopic] = Field(default_factory=list)


class CompetitorTopicsTopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sort_order: int
    brief: ArticleGenerateRequest
    source_competitors: list[str] = Field(default_factory=list)
    is_gap: bool = False
    priority: str = ""
    category: str = ""


class CompetitorTopicsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    niche: str
    language: str
    audience: str
    status: ContentPlanStatus
    context: dict[str, Any] = Field(default_factory=dict)
    topics: list[CompetitorTopicsTopicResponse] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class CompetitorTopicsListResponse(BaseModel):
    items: list[CompetitorTopicsResponse]
    total: int


class CompetitorTopicsErrorResponse(BaseModel):
    """Sanitized competitor-topic failure. Never contains secrets."""

    detail: str
    id: uuid.UUID | None = None
    status: ContentPlanStatus | None = None


CompetitorTopicsExportRequest = DiscoveryExportRequest
CompetitorTopicsExportResponse = DiscoveryExportResponse


def _topic_response(row: object) -> CompetitorTopicsTopicResponse:
    brief_raw: Any = getattr(row, "brief")
    brief = ArticleGenerateRequest.model_validate(brief_raw)
    return CompetitorTopicsTopicResponse(
        id=getattr(row, "id"),
        sort_order=getattr(row, "sort_order"),
        brief=brief,
        source_competitors=list(getattr(row, "source_competitors") or []),
        is_gap=bool(getattr(row, "is_gap", False)),
        priority=str(getattr(row, "priority") or ""),
        category=str(getattr(row, "category") or ""),
    )


def competitor_topics_response(
    plan: object, topics: list[object] | None = None
) -> CompetitorTopicsResponse:
    rows = topics if topics is not None else list(getattr(plan, "topics") or [])
    return CompetitorTopicsResponse(
        id=getattr(plan, "id"),
        source=str(getattr(plan, "source") or ContentPlanSource.COMPETITOR_GAP.value),
        niche=getattr(plan, "niche"),
        language=getattr(plan, "language"),
        audience=getattr(plan, "audience"),
        status=getattr(plan, "status"),
        context=dict(getattr(plan, "context") or {}),
        topics=[_topic_response(row) for row in rows],
        error_message=getattr(plan, "error_message"),
        created_at=getattr(plan, "created_at"),
        updated_at=getattr(plan, "updated_at"),
    )
