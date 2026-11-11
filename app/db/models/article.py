"""Article ORM model and status enum."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.models.project import project_id_column


class ArticleStatus(enum.StrEnum):
    """Allowed article lifecycle statuses."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(enum.StrEnum):
    """Operator verdict. Not a CMS publish state."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Article(Base):
    """Persisted article generation record."""

    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = project_id_column()
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'ru'"),
        default="ru",
    )
    audience: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'general'"),
        default="general",
    )
    keywords: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ArticleStatus] = mapped_column(
        Enum(
            ArticleStatus,
            name="article_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            native_enum=True,
        ),
        nullable=False,
        server_default=text("'pending'::article_status"),
        default=ArticleStatus.PENDING,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Stage 4 compact agent trace (steps/verdict only — no article body).
    pipeline: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Stage 5 — generated image metadata and inserted internal links.
    assets: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    internal_links: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Stage 6 — shorter Dzen version (title, markdown, assets metadata).
    dzen: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Stage 6 — detector scores, humanizer flag, summary text (no article body).
    quality: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Stage 3 — analyzed competitor URLs (no page HTML).
    competitor_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus,
            name="review_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            native_enum=True,
        ),
        nullable=False,
        server_default=text("'pending'::review_status"),
        default=ReviewStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
