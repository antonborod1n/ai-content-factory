"""Request and response schemas for the article API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.article import Article, ArticleStatus, ReviewStatus
from app.schemas.ai import ArticleWriteInput, CompetitorSourceRef
from app.schemas.dzen import DzenArticle
from app.schemas.enrichment import ArticleAsset, InternalLinkRef
from app.schemas.pipeline import PipelineTrace
from app.schemas.quality import QualityReport


class ArticleGenerateRequest(BaseModel):
    """Body of POST /api/v1/articles/generate (matches topics/*.json brief)."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    language: str = Field(default="ru", min_length=1)
    audience: str = Field(default="general", min_length=1)
    keywords: list[str] = Field(default_factory=list)

    word_count: int | None = Field(default=None, ge=1)
    search_intent: str = "informational_commercial"
    primary_keywords: list[str] = Field(default_factory=list)
    secondary_keywords: list[str] = Field(default_factory=list)
    article_goal: str = ""
    tone: str = "экспертный, понятный, разговорный"
    include_tables: bool = True
    include_lists: bool = True
    include_faq: bool = True
    faq_count: int = Field(default=5, ge=0)
    image_placeholders: int = Field(default=3, ge=0)
    infographic_placeholders: int = Field(default=1, ge=0)
    section_image_placeholders: list[int] = Field(default_factory=list)
    cta: str = ""
    outline: list[str] = Field(default_factory=list)
    use_knowledge_base: bool = True
    use_competitor_research: bool = False
    research_id: uuid.UUID | None = None
    use_multi_agent: bool = False
    use_text: bool = True
    use_images: bool = False
    article_id: uuid.UUID | None = None
    use_internal_links: bool = True
    use_dzen: bool = False
    use_detectors: bool = False
    use_humanizer: bool = False
    use_summary: bool = False

    @field_validator("topic", "language", "audience")
    @classmethod
    def _require_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator(
        "keywords",
        "primary_keywords",
        "secondary_keywords",
        "outline",
    )
    @classmethod
    def _clean_string_lists(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @model_validator(mode="after")
    def _sync_keyword_fields(self) -> ArticleGenerateRequest:
        if not self.primary_keywords and self.keywords:
            self.primary_keywords = list(self.keywords)
        if not self.keywords and self.primary_keywords:
            self.keywords = list(self.primary_keywords)
        return self

    @model_validator(mode="after")
    def _require_text_or_images(self) -> ArticleGenerateRequest:
        if not self.use_text and not self.use_images:
            raise ValueError("enable use_text and/or use_images")
        if not self.use_text and self.article_id is None:
            raise ValueError("article_id is required when use_text is false")
        return self

    def to_write_input(self) -> ArticleWriteInput:
        return ArticleWriteInput.model_validate(
            self.model_dump(exclude_none=False)
        )


class ArticleGenerateResponse(BaseModel):
    """Successful generation result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ArticleStatus
    title: str
    meta_description: str
    url_slug: str | None = None
    content_markdown: str
    word_count: int
    pipeline: PipelineTrace | None = None
    assets: list[ArticleAsset] | None = None
    internal_links: list[InternalLinkRef] | None = None
    dzen: DzenArticle | None = None
    quality: QualityReport | None = None
    competitor_sources: list[CompetitorSourceRef] | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING


class ArticleListItem(BaseModel):
    """Catalog card for GET /articles — no markdown body."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ArticleStatus
    topic: str
    title: str = ""
    url_slug: str | None = None
    language: str
    word_count: int = 0
    review_status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime
    updated_at: datetime


class ArticleListResponse(BaseModel):
    items: list[ArticleListItem]
    total: int


class ArticleErrorResponse(BaseModel):
    """Sanitized failure payload. Never contains secrets or stack traces."""

    detail: str
    id: uuid.UUID | None = None
    status: ArticleStatus = ArticleStatus.FAILED


def article_list_item(article: Article) -> ArticleListItem:
    return ArticleListItem(
        id=article.id,
        status=article.status,
        topic=article.topic,
        title=article.title or "",
        url_slug=article.url_slug,
        language=article.language or "ru",
        word_count=article.word_count or 0,
        review_status=article.review_status or ReviewStatus.PENDING,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


def article_detail_response(article: Article) -> ArticleGenerateResponse:
    """Map an ORM row, including pending/failed drafts with empty body fields."""
    return ArticleGenerateResponse.model_validate(
        {
            "id": article.id,
            "status": article.status,
            "title": article.title or "",
            "meta_description": article.meta_description or "",
            "url_slug": article.url_slug,
            "content_markdown": article.content_markdown or "",
            "word_count": article.word_count or 0,
            "pipeline": article.pipeline,
            "assets": article.assets,
            "internal_links": article.internal_links,
            "dzen": article.dzen,
            "quality": article.quality,
            "competitor_sources": article.competitor_sources,
            "review_status": article.review_status or ReviewStatus.PENDING,
        }
    )


class ArticleReviewRequest(BaseModel):
    """Operator verdict. Does not publish the article."""

    model_config = ConfigDict(extra="forbid")

    review_status: ReviewStatus
