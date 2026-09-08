from functools import lru_cache

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
    # Required: credentials must come from the environment, never from code.
    database_url: str
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    openai_temperature: float = 0.4
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
