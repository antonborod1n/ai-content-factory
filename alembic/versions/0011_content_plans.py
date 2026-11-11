"""create topic discovery content plan tables

Revision ID: 0011_content_plans
Revises: 0010_section_images
Create Date: 2026-09-13 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_content_plans"
down_revision: str | None = "0010_section_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

content_plan_status_enum = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="content_plan_status",
    create_type=False,
)


def upgrade() -> None:
    content_plan_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "content_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("niche", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "seeds",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "engines_used",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.String(length=10),
            server_default=sa.text("'ru'"),
            nullable=False,
        ),
        sa.Column(
            "audience",
            sa.Text(),
            server_default=sa.text("'general'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            content_plan_status_enum,
            server_default=sa.text("'pending'::content_plan_status"),
            nullable=False,
        ),
        sa.Column(
            "candidates",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "content_plan_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "brief",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_engines",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_queries",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["content_plans.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_plan_topics_plan_id",
        "content_plan_topics",
        ["plan_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_plan_topics_plan_id",
        table_name="content_plan_topics",
    )
    op.drop_table("content_plan_topics")
    op.drop_table("content_plans")
    content_plan_status_enum.drop(op.get_bind(), checkfirst=True)
