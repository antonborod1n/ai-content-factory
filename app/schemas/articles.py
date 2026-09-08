"""Request and response schemas for the article API."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.article import ArticleStatus
from app.schemas.ai import ArticleWriteInput


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
    cta: str = ""
    outline: list[str] = Field(default_factory=list)

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


class ArticleErrorResponse(BaseModel):
    """Sanitized failure payload. Never contains secrets or stack traces."""

    detail: str
    id: uuid.UUID | None = None
    status: ArticleStatus = ArticleStatus.FAILED
