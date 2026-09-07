"""AI-related Pydantic schemas."""

from pydantic import BaseModel, ConfigDict, Field


class ArticleWriteInput(BaseModel):
    """Input contract for AIWriter.generate."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    language: str = "ru"
    audience: str = "general"
    keywords: list[str] = Field(default_factory=list)


class AIArticleOutput(BaseModel):
    """Structured AI article payload (validated before persistence)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    meta_description: str = Field(min_length=1)
    content_markdown: str = Field(min_length=1)
    word_count: int = Field(ge=0)
