"""add articles.pipeline jsonb for Stage 4 agent trace

Revision ID: 0005_article_pipeline
Revises: 0004_competitor_research
Create Date: 2026-09-11 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_article_pipeline"
down_revision: str | None = "0004_competitor_research"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("pipeline", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("articles", "pipeline")
