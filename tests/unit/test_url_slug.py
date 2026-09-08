"""Tests for URL slug normalization."""

import uuid

from app.core.url_slug import normalize_url_slug


def test_normalize_keeps_latin_slug() -> None:
    article_id = uuid.uuid4()
    assert (
        normalize_url_slug(
            "Zhestkiy-ili-Myagkiy-Matras!",
            article_id=article_id,
        )
        == "zhestkiy-ili-myagkiy-matras"
    )


def test_normalize_falls_back_when_empty() -> None:
    article_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert (
        normalize_url_slug("   ", article_id=article_id)
        == "article-12345678"
    )


def test_normalize_strips_cyrillic_to_fallback_or_hyphens() -> None:
    article_id = uuid.uuid4()
    # Pure Cyrillic becomes empty after latin-only filter → fallback.
    assert normalize_url_slug("Матрас мягкий", article_id=article_id).startswith(
        "article-"
    )
