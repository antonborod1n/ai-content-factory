"""Stage 6 Dzen channel DTOs (shorter version of the main article)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ai import MODEL_OUTPUT_CONFIG
from app.schemas.enrichment import ArticleAsset, GeneratedAsset


class DzenWriteInput(BaseModel):
    """Input for DzenWriter: main article title + body, shorter length."""

    model_config = ConfigDict(extra="forbid")

    source_title: str = Field(min_length=1)
    source_markdown: str = Field(min_length=1)
    language: str = "ru"
    audience: str = "general"
    target_char_count: int = Field(default=4000, ge=200)


class DzenArticleOutput(BaseModel):
    """Structured Dzen draft from the AI layer (length recalculated later)."""

    model_config = MODEL_OUTPUT_CONFIG

    title: str = Field(min_length=1)
    content_markdown: str = Field(min_length=1)
    char_count: int = Field(ge=0)


class DzenArticle(BaseModel):
    """Persisted / API Dzen payload. No image bytes."""

    model_config = ConfigDict(extra="forbid")

    status: str
    title: str = ""
    content_markdown: str = ""
    char_count: int = 0
    assets: list[ArticleAsset] = Field(default_factory=list)


class DzenWriteResult(BaseModel):
    """Runtime result including bytes for the disk write."""

    model_config = ConfigDict(extra="forbid")

    article: DzenArticle
    assets: list[GeneratedAsset] = Field(default_factory=list)
