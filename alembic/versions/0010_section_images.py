"""store competitor photos per heading and planned slots per outline section

Revision ID: 0010_section_images
Revises: 0009_article_competitor_sources
Create Date: 2026-09-12 10:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_section_images"
down_revision: str | None = "0009_article_competitor_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_runs",
        sa.Column(
            "section_image_placeholders",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "research_competitors",
        sa.Column(
            "section_images",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("research_competitors", "section_images")
    op.drop_column("research_runs", "section_image_placeholders")
