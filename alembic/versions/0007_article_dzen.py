"""add articles.dzen for Stage 6 Dzen channel version

Revision ID: 0007_article_dzen
Revises: 0006_article_assets
Create Date: 2026-09-11 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_article_dzen"
down_revision: str | None = "0006_article_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("dzen", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("articles", "dzen")
