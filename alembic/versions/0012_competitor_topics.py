"""add content plan source and competitor-gap topic metadata

Revision ID: 0012_competitor_topics
Revises: 0011_content_plans
Create Date: 2026-09-15 12:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_competitor_topics"
down_revision: str | None = "0011_content_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_plans",
        sa.Column(
            "source",
            sa.String(length=32),
            server_default="serp",
            nullable=False,
        ),
    )
    op.add_column(
        "content_plans",
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_content_plans_source",
        "content_plans",
        ["source"],
    )
    op.add_column(
        "content_plan_topics",
        sa.Column(
            "source_competitors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "content_plan_topics",
        sa.Column(
            "is_gap",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "content_plan_topics",
        sa.Column(
            "priority",
            sa.String(length=16),
            server_default=sa.text("''"),
            nullable=False,
        ),
    )
    op.add_column(
        "content_plan_topics",
        sa.Column(
            "category",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("content_plan_topics", "category")
    op.drop_column("content_plan_topics", "priority")
    op.drop_column("content_plan_topics", "is_gap")
    op.drop_column("content_plan_topics", "source_competitors")
    op.drop_index("ix_content_plans_source", table_name="content_plans")
    op.drop_column("content_plans", "context")
    op.drop_column("content_plans", "source")
