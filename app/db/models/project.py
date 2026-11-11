"""Client project. Isolates knowledge, topics, articles, and research."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base

DEFAULT_PROJECT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
DEFAULT_PROJECT_SLUG = "default"


def project_id_column() -> Mapped[uuid.UUID]:
    """Foreign key to ``projects``. Existing rows belong to the default project."""
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_PROJECT_ID,
    )


class Project(Base):
    """One client site: its own KB, articles, research, and topic file."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'ru'"),
        default="ru",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
