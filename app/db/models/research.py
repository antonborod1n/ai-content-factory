"""ORM models for Stage 3 competitor research."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base
from app.db.models.project import project_id_column


class ResearchStatus(enum.StrEnum):
    """Lifecycle of a competitor-research run."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchRun(Base):
    """One SERP research + improved outline for a topic."""

    __tablename__ = "research_runs"

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
    query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[ResearchStatus] = mapped_column(
        Enum(
            ResearchStatus,
            name="research_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            native_enum=True,
        ),
        nullable=False,
        server_default=text("'pending'::research_status"),
        default=ResearchStatus.PENDING,
    )
    outline: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    section_image_placeholders: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    title_hint: Mapped[str] = mapped_column(Text, nullable=False, default="")
    meta_description_hint: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    url_slug_hint: Mapped[str] = mapped_column(Text, nullable=False, default="")
    article_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    competitors: Mapped[list[ResearchCompetitor]] = relationship(
        back_populates="research",
        cascade="all, delete-orphan",
        order_by="ResearchCompetitor.rank",
    )


class ResearchCompetitor(Base):
    """One organic result plus extracted structure (no raw HTML)."""

    __tablename__ = "research_competitors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    research_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    headings: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    section_images: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    list_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_faq: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    features: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    fetch_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    research: Mapped[ResearchRun] = relationship(back_populates="competitors")
