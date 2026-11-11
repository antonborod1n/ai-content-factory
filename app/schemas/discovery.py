"""Schemas for Topic Discovery (SERP → content plan)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.project_paths import confined_topics_path
from app.db.models.discovery import ContentPlanStatus
from app.schemas.ai import MODEL_OUTPUT_CONFIG
from app.schemas.articles import ArticleGenerateRequest


class SearchEngine(enum.StrEnum):
    """Supported SERP engines for topic discovery."""

    GOOGLE = "google"
    YANDEX = "yandex"


class CandidateKind(enum.StrEnum):
    """Where a topic candidate came from inside a SERP snapshot."""

    ORGANIC = "organic"
    PAA = "paa"
    RELATED = "related"


class SerpOrganicHit(BaseModel):
    """One organic row from a SERP snapshot (no page body)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    snippet: str = ""
    rank: int = Field(ge=1)


class SerpSnapshot(BaseModel):
    """Normalized Google or Yandex SERP snapshot."""

    model_config = ConfigDict(extra="forbid")

    engine: SearchEngine
    query: str
    organic: list[SerpOrganicHit] = Field(default_factory=list)
    people_also_ask: list[str] = Field(default_factory=list)
    related_searches: list[str] = Field(default_factory=list)


class TopicCandidate(BaseModel):
    """One flattened SERP signal used for clustering."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    kind: CandidateKind
    engine: SearchEngine
    query: str
    url: str = ""


class TopicBriefDraft(BaseModel):
    """Planner output for one article topic (defaults applied later)."""

    model_config = MODEL_OUTPUT_CONFIG

    topic: str = Field(min_length=1)
    primary_keywords: list[str] = Field(default_factory=list)
    secondary_keywords: list[str] = Field(default_factory=list)
    article_goal: str = ""
    outline: list[str] = Field(default_factory=list)
    search_intent: str = "informational_commercial"

    @field_validator("topic", "article_goal", "search_intent")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("primary_keywords", "secondary_keywords", "outline")
    @classmethod
    def _clean_lists(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class TopicPlanInput(BaseModel):
    """Input for TopicPlanner (AI layer)."""

    model_config = ConfigDict(extra="forbid")

    niche: str = ""
    seeds: list[str] = Field(min_length=1)
    language: str = "ru"
    audience: str = "general"
    max_topics: int = Field(ge=1, le=30)
    candidates: list[TopicCandidate] = Field(default_factory=list)


class TopicPlanOutput(BaseModel):
    """Clustered article briefs from SERP candidates."""

    model_config = MODEL_OUTPUT_CONFIG

    topics: list[TopicBriefDraft] = Field(default_factory=list)


class DiscoveryRequest(BaseModel):
    """Body of POST /api/v1/discovery."""

    model_config = ConfigDict(extra="forbid")

    seeds: list[str] = Field(min_length=1)
    niche: str = ""
    language: str = Field(default="ru", min_length=1)
    audience: str = Field(default="general", min_length=1)
    max_topics: int | None = Field(default=None, ge=1, le=30)
    engines: list[SearchEngine] = Field(
        default_factory=lambda: [SearchEngine.GOOGLE, SearchEngine.YANDEX]
    )
    word_count: int | None = Field(default=None, ge=1)
    tone: str = "экспертный, понятный, разговорный"
    search_intent: str = "informational_commercial"
    use_knowledge_base: bool = True
    use_competitor_research: bool = False
    use_multi_agent: bool = False
    use_text: bool = True
    use_images: bool = False
    use_internal_links: bool = True
    use_dzen: bool = False
    use_detectors: bool = False
    use_humanizer: bool = False
    use_summary: bool = False

    @field_validator("language", "audience")
    @classmethod
    def _require_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("tone", "search_intent", "niche")
    @classmethod
    def _strip_optional_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("seeds")
    @classmethod
    def _clean_seeds(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("engines")
    @classmethod
    def _unique_engines(cls, value: list[SearchEngine]) -> list[SearchEngine]:
        seen: set[SearchEngine] = set()
        unique: list[SearchEngine] = []
        for engine in value:
            if engine not in seen:
                seen.add(engine)
                unique.append(engine)
        if not unique:
            raise ValueError("at least one engine is required")
        return unique


class DiscoveryExportRequest(BaseModel):
    """Optional override for POST /api/v1/discovery/{id}/export."""

    model_config = ConfigDict(extra="forbid")

    path: str | None = None

    @field_validator("path")
    @classmethod
    def path_stays_in_topics_dir(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return str(confined_topics_path(value))


class ContentPlanTopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sort_order: int
    brief: ArticleGenerateRequest
    source_engines: list[str] = Field(default_factory=list)
    source_queries: list[str] = Field(default_factory=list)


class DiscoveryResponse(BaseModel):
    """Stored content plan."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    niche: str
    seeds: list[str]
    engines_used: list[str]
    language: str
    audience: str
    status: ContentPlanStatus
    candidates: list[TopicCandidate] = Field(default_factory=list)
    topics: list[ContentPlanTopicResponse] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DiscoveryListResponse(BaseModel):
    items: list[DiscoveryResponse]
    total: int


class DiscoveryExportResponse(BaseModel):
    path: str
    added: int
    skipped: int


class DiscoveryErrorResponse(BaseModel):
    """Sanitized discovery failure. Never contains secrets."""

    detail: str
    id: uuid.UUID | None = None
    status: ContentPlanStatus | None = None


def _topic_response(row: object) -> ContentPlanTopicResponse:
    brief_raw: Any = getattr(row, "brief")
    brief = ArticleGenerateRequest.model_validate(brief_raw)
    return ContentPlanTopicResponse(
        id=getattr(row, "id"),
        sort_order=getattr(row, "sort_order"),
        brief=brief,
        source_engines=list(getattr(row, "source_engines") or []),
        source_queries=list(getattr(row, "source_queries") or []),
    )


def discovery_response(plan: object, topics: list[object] | None = None) -> DiscoveryResponse:
    rows = topics if topics is not None else list(getattr(plan, "topics") or [])
    raw_candidates = getattr(plan, "candidates") or []
    candidates = [
        TopicCandidate.model_validate(item) if not isinstance(item, TopicCandidate) else item
        for item in raw_candidates
    ]
    return DiscoveryResponse(
        id=getattr(plan, "id"),
        niche=getattr(plan, "niche"),
        seeds=list(getattr(plan, "seeds") or []),
        engines_used=list(getattr(plan, "engines_used") or []),
        language=getattr(plan, "language"),
        audience=getattr(plan, "audience"),
        status=getattr(plan, "status"),
        candidates=candidates,
        topics=[_topic_response(row) for row in rows],
        error_message=getattr(plan, "error_message"),
        created_at=getattr(plan, "created_at"),
        updated_at=getattr(plan, "updated_at"),
    )
