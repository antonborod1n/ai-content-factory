"""Operator-facing runtime facts. Never includes secrets."""

from __future__ import annotations

from app.config import get_settings


def runtime_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "openai_configured": bool(settings.openai_api_key.strip()),
        "openai_model": settings.openai_model,
        "serp_configured": bool(settings.serp_api_key.strip()),
        "yandex_configured": bool(settings.yandex_serp_api_key.strip()),
        "images_enabled": settings.images_enabled,
        "discovery_enabled": settings.discovery_enabled,
        "image_model": settings.openai_image_model,
        "article_target_word_count": settings.article_target_word_count,
        "app_env": settings.app_env,
        "openai_temperature": settings.openai_temperature,
        "openai_max_tokens": settings.openai_max_tokens,
        "openai_base_url_configured": bool((settings.openai_base_url or "").strip()),
        "embedding_model": settings.openai_embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "rag_enabled": settings.rag_enabled,
        "rag_top_k": settings.rag_top_k,
        "rag_chunk_size": settings.rag_chunk_size,
        "rag_chunk_overlap": settings.rag_chunk_overlap,
        "serp_provider": settings.serp_provider,
        "research_enabled": settings.research_enabled,
        "research_top_n": settings.research_top_n,
        "research_search_n": settings.research_search_n,
        "discovery_max_topics": settings.discovery_max_topics,
        "discovery_search_n": settings.discovery_search_n,
        "yandex_serp_provider": settings.yandex_serp_provider,
        "competitor_topics_enabled": settings.competitor_topics_enabled,
        "competitor_topics_max_topics": settings.competitor_topics_max_topics,
        "multi_agent_enabled": settings.multi_agent_enabled,
        "image_size": settings.openai_image_size,
        "internal_links_enabled": settings.internal_links_enabled,
        "internal_link_max": settings.internal_link_max,
        "internal_link_prefix": settings.internal_link_prefix,
        "dzen_enabled": settings.dzen_enabled,
        "dzen_target_char_count": settings.dzen_target_char_count,
        "quality_enabled": settings.quality_enabled,
        "detector_ai_review_threshold": settings.detector_ai_review_threshold,
        "detector_uniqueness_floor": settings.detector_uniqueness_floor,
        "summary_target_char_count": settings.summary_target_char_count,
        "article_min_word_ratio": settings.article_min_word_ratio,
        "article_expand_attempts": settings.article_expand_attempts,
        "articles_output_dir": settings.articles_output_dir,
    }
