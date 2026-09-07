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
    # ~1800 words of Russian markdown needs well over 4000 completion tokens.
    openai_max_tokens: int | None = 8000
    article_target_word_count: int = 1800
    prompts_dir: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
