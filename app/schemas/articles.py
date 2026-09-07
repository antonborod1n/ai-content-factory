"""Request and response schemas for the article API."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.article import ArticleStatus
from app.schemas.ai import ArticleWriteInput


class ArticleGenerateRequest(BaseModel):
    """Body of POST /api/v1/articles/generate."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    language: str = Field(default="ru", min_length=1)
    audience: str = Field(default="general", min_length=1)
    keywords: list[str] = Field(default_factory=list)

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
        return [keyword.strip() for keyword in value if keyword.strip()]

    def to_write_input(self) -> ArticleWriteInput:
        return ArticleWriteInput(
            topic=self.topic,
            language=self.language,
            audience=self.audience,
            keywords=self.keywords,
        )


class ArticleGenerateResponse(BaseModel):
    """Successful generation result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ArticleStatus
    title: str
    meta_description: str
    content_markdown: str
    word_count: int


class ArticleErrorResponse(BaseModel):
    """Sanitized failure payload. Never contains secrets or stack traces."""

    detail: str
    id: uuid.UUID | None = None
    status: ArticleStatus = ArticleStatus.FAILED
