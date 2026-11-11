"""add articles.assets and articles.internal_links for Stage 5

Revision ID: 0006_article_assets
Revises: 0005_article_pipeline
Create Date: 2026-09-11 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_article_assets"
down_revision: str | None = "0005_article_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("assets", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column(
            "internal_links",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("articles", "internal_links")
    op.drop_column("articles", "assets")
