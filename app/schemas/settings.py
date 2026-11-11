"""Responses for operator settings. No secrets."""

from pydantic import BaseModel, ConfigDict


class RuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    openai_configured: bool
    openai_model: str
    serp_configured: bool
    yandex_configured: bool
    images_enabled: bool
    discovery_enabled: bool
    image_model: str
    article_target_word_count: int
    app_env: str
    openai_temperature: float
    openai_max_tokens: int | None
    openai_base_url_configured: bool
    embedding_model: str
    embedding_dimensions: int
    rag_enabled: bool
    rag_top_k: int
    rag_chunk_size: int
    rag_chunk_overlap: int
    serp_provider: str
    research_enabled: bool
    research_top_n: int
    research_search_n: int
    discovery_max_topics: int
    discovery_search_n: int
    yandex_serp_provider: str
    competitor_topics_enabled: bool
    competitor_topics_max_topics: int
    multi_agent_enabled: bool
    image_size: str
    internal_links_enabled: bool
    internal_link_max: int
    internal_link_prefix: str
    dzen_enabled: bool
    dzen_target_char_count: int
    quality_enabled: bool
    detector_ai_review_threshold: int
    detector_uniqueness_floor: int
    summary_target_char_count: int
    article_min_word_ratio: float
    article_expand_attempts: int
    articles_output_dir: str


class PromptListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str


class PromptDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    content: str
