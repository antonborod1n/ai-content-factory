"""add articles.quality for Stage 6 detectors / humanizer / summary

Revision ID: 0008_article_quality
Revises: 0007_article_dzen
Create Date: 2026-09-11 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_article_quality"
down_revision: str | None = "0007_article_dzen"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("quality", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("articles", "quality")
