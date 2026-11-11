"""ORM models for Topic Discovery content plans."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base
from app.db.models.project import project_id_column


class ContentPlanStatus(enum.StrEnum):
    """Lifecycle of a topic-discovery run."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ContentPlanSource(enum.StrEnum):
    """How the content plan was produced."""

    SERP = "serp"
    COMPETITOR_GAP = "competitor_gap"


class ContentPlan(Base):
    """One SERP snapshot or competitor-inventory plan + article briefs."""

    __tablename__ = "content_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = project_id_column()
    niche: Mapped[str] = mapped_column(Text, nullable=False, default="")
    seeds: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    engines_used: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
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
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'serp'"),
        default=ContentPlanSource.SERP.value,
    )
    context: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    status: Mapped[ContentPlanStatus] = mapped_column(
        Enum(
            ContentPlanStatus,
            name="content_plan_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            native_enum=True,
        ),
        nullable=False,
        server_default=text("'pending'::content_plan_status"),
        default=ContentPlanStatus.PENDING,
    )
    candidates: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
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

    topics: Mapped[list[ContentPlanTopic]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ContentPlanTopic.sort_order",
    )


class ContentPlanTopic(Base):
    """One article brief produced from a content plan."""

    __tablename__ = "content_plan_topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    brief: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    source_engines: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    source_queries: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    source_competitors: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list,
    )
    is_gap: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    priority: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("''"),
        default="",
    )
    category: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    plan: Mapped[ContentPlan] = relationship(back_populates="topics")
