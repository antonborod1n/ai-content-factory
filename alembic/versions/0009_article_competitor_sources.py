"""add articles.competitor_sources for analyzed competitor URLs

Revision ID: 0009_article_competitor_sources
Revises: 0008_article_quality
Create Date: 2026-09-12 08:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_article_competitor_sources"
down_revision: str | None = "0008_article_quality"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column(
            "competitor_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("articles", "competitor_sources")
