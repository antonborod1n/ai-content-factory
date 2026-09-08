"""add url_slug to articles

Revision ID: 0002_add_url_slug
Revises: 0001_create_articles
Create Date: 2026-09-07 17:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_url_slug"
down_revision: str | None = "0001_create_articles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("url_slug", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("articles", "url_slug")
