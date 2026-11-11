"""AI-related Pydantic schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Parsed model replies: an extra key (e.g. "reasoning") must not fail the step.
# API request bodies stay extra="forbid".
MODEL_OUTPUT_CONFIG = ConfigDict(extra="ignore")


class CompetitorSourceRef(BaseModel):
    """One analyzed competitor URL (no page body)."""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(default=0, ge=0)
    title: str = ""
    url: str = Field(min_length=1)


class SectionImageCount(BaseModel):
    """Photos counted under one competitor heading."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    image_count: int = Field(default=0, ge=0)


class ArticleWriteInput(BaseModel):
    """Input contract for AIWriter.generate (brief + legacy fields)."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    language: str = "ru"
    audience: str = "general"
    # Legacy flat list; kept in sync with primary_keywords when possible.
    keywords: list[str] = Field(default_factory=list)

    # Target length for the prompt (backend still recalculates the stored count).
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
    # Per-outline photo counts from competitor averages. Empty = even spread.
    section_image_placeholders: list[int] = Field(default_factory=list)
    competitor_image_sections: list[list[SectionImageCount]] = Field(
        default_factory=list
    )
    cta: str = ""
    outline: list[str] = Field(default_factory=list)
    # Filled by ArticleService from the knowledge base; not an API field.
    knowledge_context: str = ""
    use_knowledge_base: bool = True
    # Stage 3 — competitor research. research_id / flag are API fields;
    # competitor_context is filled by ArticleService after research.
    use_competitor_research: bool = False
    research_id: uuid.UUID | None = None
    competitor_context: str = ""
    # Filled by ResearchService after SERP; persisted and written to article.md.
    competitor_sources: list[CompetitorSourceRef] = Field(default_factory=list)
    # Stage 4 — run Research → SEO → Writer → Fact Checker → Editor.
    use_multi_agent: bool = False
    # Stage 5 — replace placeholders with generated images; link other articles.
    use_text: bool = True
    use_images: bool = False
    # Existing article for images-only regenerate (use_text=false).
    article_id: uuid.UUID | None = None
    use_internal_links: bool = True
    # Stage 6 — shorter Dzen version of the same article (from the main title).
    use_dzen: bool = False
    # Stage 6 quality — detectors, humanizer, short summary (all opt-in).
    use_detectors: bool = False
    use_humanizer: bool = False
    use_summary: bool = False

    @model_validator(mode="after")
    def _sync_keyword_fields(self) -> ArticleWriteInput:
        if not self.primary_keywords and self.keywords:
            self.primary_keywords = list(self.keywords)
        if not self.keywords and self.primary_keywords:
            self.keywords = list(self.primary_keywords)
        return self

    def keywords_for_storage(self) -> list[str]:
        """Primary + secondary keywords for the articles.keywords column."""
        seen: set[str] = set()
        merged: list[str] = []
        for keyword in (
            *self.primary_keywords,
            *self.secondary_keywords,
            *self.keywords,
        ):
            cleaned = keyword.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                merged.append(cleaned)
        return merged

    def brief_for_prompt(self, *, default_word_count: int) -> dict:
        """JSON plan block embedded into the user prompt."""
        return {
            "topic": self.topic,
            "language": self.language,
            "audience": self.audience,
            "word_count": self.word_count or default_word_count,
            "search_intent": self.search_intent,
            "primary_keywords": self.primary_keywords,
            "secondary_keywords": self.secondary_keywords,
            "article_goal": self.article_goal,
            "tone": self.tone,
            "include_tables": self.include_tables,
            "include_lists": self.include_lists,
            "include_faq": self.include_faq,
            "faq_count": self.faq_count,
            "image_placeholders": self.image_placeholders,
            "infographic_placeholders": self.infographic_placeholders,
            "section_image_placeholders": self.section_image_placeholders,
            "cta": self.cta,
            "outline": self.outline,
        }


class CompetitorPlanOutput(BaseModel):
    """Improved outline and SEO hints from competitor analysis."""

    model_config = MODEL_OUTPUT_CONFIG

    outline: list[str] = Field(min_length=2)
    title_hint: str = ""
    meta_description_hint: str = ""
    url_slug_hint: str = ""
    article_goal: str = ""
    notes: str = ""


class AIArticleMetaOutput(BaseModel):
    """SEO wrapper returned before the body is written section by section."""

    model_config = MODEL_OUTPUT_CONFIG

    title: str = Field(min_length=1)
    meta_description: str = Field(min_length=1)
    url_slug: str = Field(default="")


class AISectionOutput(BaseModel):
    """Markdown of a single article section."""

    model_config = MODEL_OUTPUT_CONFIG

    content_markdown: str = Field(min_length=1)


class AIArticleOutput(BaseModel):
    """Structured AI article payload (validated before persistence)."""

    model_config = MODEL_OUTPUT_CONFIG

    title: str = Field(min_length=1)
    meta_description: str = Field(min_length=1)
    content_markdown: str = Field(min_length=1)
    word_count: int = Field(ge=0)
    url_slug: str = Field(
        default="",
        description="SEO URL slug: lowercase latin, digits, hyphens",
    )
