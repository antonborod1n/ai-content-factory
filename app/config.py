from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    # Empty = derive from APP_ENV (test → WARNING, otherwise INFO).
    log_level: str = ""
    # Comma-separated browser origins for the Stage 8a operator UI (Vite).
    # Empty disables CORS middleware.
    app_cors_origins: str = "http://localhost:15173,http://127.0.0.1:15173"
    # Required: credentials must come from the environment, never from code.
    database_url: str
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    openai_temperature: float = 0.4
    # One model call. The client retries once, then the job is marked failed.
    openai_timeout_seconds: float = 300.0
    # ~3000 words of Russian markdown needs a large completion budget.
    openai_max_tokens: int | None = 16000
    article_target_word_count: int = 3000
    # Small models undershoot the target, so a short draft is sent back for
    # expansion until it reaches ratio * target (0 disables the extra calls).
    article_min_word_ratio: float = 0.8
    article_expand_attempts: int = 2
    prompts_dir: str | None = None
    # Completed articles are also written here as Markdown. Empty = disabled.
    articles_output_dir: str = "output/articles"
    # JSONL journal of task runs. Empty disables the file.
    runs_log_path: str = "logs/runs.jsonl"
    # Per-file cap for knowledge-base and competitor uploads.
    max_upload_mb: int = Field(default=20, ge=1)

    # Stage 2 — Knowledge Base / RAG. Embedding calls use the same API key
    # and optional OPENAI_BASE_URL as article generation.
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    rag_enabled: bool = True
    rag_top_k: int = 5
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_max_file_bytes: int = 2_000_000

    # Stage 3 — competitor SERP research. Search uses SERP_API_KEY (Serper).
    # Page fetch is plain HTTP. Outline planning uses OPENAI_API_KEY.
    serp_provider: str = "serper"
    serp_api_key: str = ""
    serp_base_url: str = "https://google.serper.dev/search"
    research_enabled: bool = True
    research_top_n: int = 10
    # Pull extra SERP rows (with pagination), then keep RESEARCH_TOP_N articles.
    research_search_n: int = 40
    research_min_article_chars: int = 300
    research_fetch_timeout_seconds: float = 15.0
    research_max_page_bytes: int = 1_000_000
    research_user_agent: str = "AI-Content-Factory/0.1 (+research)"

    # Topic Discovery — Google (Serper) + Yandex (SerpAPI) snapshots → briefs.
    discovery_enabled: bool = True
    discovery_max_topics: int = 10
    discovery_search_n: int = 20
    yandex_serp_provider: str = "serpapi"
    yandex_serp_api_key: str = ""
    yandex_serp_base_url: str = "https://serpapi.com/search"
    topics_file_path: str = "topics/topics.json"
    # Root for per-project topic files and the only place exports may write.
    topics_dir: str = "topics"

    # Competitor-inventory content plans (xlsx/JSON dumps → topics.json).
    competitor_topics_enabled: bool = True
    competitor_topics_max_topics: int = 80
    competitor_topics_max_hits: int = 400

    # Stage 4 — multi-agent generate (research → SEO → writer → fact-check → editor).
    # Per-request flag use_multi_agent still defaults to false.
    multi_agent_enabled: bool = True

    # Stage 5 — real images (OpenAI Images) and internal links between articles.
    images_enabled: bool = True
    openai_image_model: str = "x-ai/grok-imagine-image-2.0"
    openai_image_size: str = "1792x1024"
    internal_links_enabled: bool = True
    internal_link_max: int = 5
    internal_link_prefix: str = "/"

    # Stage 6 (Dzen only) — shorter channel version from the main article title.
    # Per-request flag use_dzen still defaults to false.
    dzen_enabled: bool = True
    dzen_target_char_count: int = 4000

    # Stage 6 quality — detectors / humanizer / summary (opt-in per request).
    quality_enabled: bool = True
    detector_ai_review_threshold: int = 70
    detector_uniqueness_floor: int = 50
    summary_target_char_count: int = 500


    def cors_origin_list(self) -> list[str]:
        return [
            part.strip()
            for part in self.app_cors_origins.split(",")
            if part.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
