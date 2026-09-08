"""Unit tests for the Article model and status enum."""

import uuid

from sqlalchemy import Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.models.article import Article, ArticleStatus


def test_article_status_values() -> None:
    assert {status.value for status in ArticleStatus} == {
        "pending",
        "processing",
        "completed",
        "failed",
    }


def test_article_tablename() -> None:
    assert Article.__tablename__ == "articles"


def test_article_columns() -> None:
    columns = Article.__table__.columns
    assert set(columns.keys()) == {
        "id",
        "topic",
        "language",
        "audience",
        "keywords",
        "title",
        "meta_description",
        "url_slug",
        "content_markdown",
        "word_count",
        "status",
        "error_message",
        "created_at",
        "updated_at",
    }
    assert isinstance(columns["id"].type, UUID)
    assert isinstance(columns["topic"].type, Text)
    assert columns["language"].type.length == 10
    assert isinstance(columns["keywords"].type, JSONB)
    assert isinstance(columns["word_count"].type, Integer)
    assert columns["title"].nullable is True
    assert columns["meta_description"].nullable is True
    assert columns["url_slug"].nullable is True
    assert columns["url_slug"].type.length == 120
    assert columns["content_markdown"].nullable is True
    assert columns["word_count"].nullable is True
    assert columns["error_message"].nullable is True
    assert columns["topic"].nullable is False
    assert columns["status"].nullable is False


def test_article_instance_fields() -> None:
    article_id = uuid.uuid4()
    article = Article(
        id=article_id,
        topic="Test topic",
        language="en",
        audience="Engineers",
        keywords=["pump"],
        status=ArticleStatus.PROCESSING,
        title=None,
        meta_description=None,
        url_slug=None,
        content_markdown=None,
        word_count=None,
        error_message=None,
    )
    assert article.id == article_id
    assert article.topic == "Test topic"
    assert article.language == "en"
    assert article.audience == "Engineers"
    assert article.keywords == ["pump"]
    assert article.status is ArticleStatus.PROCESSING
    assert article.title is None
    assert article.meta_description is None
    assert article.url_slug is None
    assert article.content_markdown is None
    assert article.word_count is None
    assert article.error_message is None
