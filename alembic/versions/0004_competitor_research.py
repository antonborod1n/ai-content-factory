"""create competitor research tables

Revision ID: 0004_competitor_research
Revises: 0003_knowledge_base
Create Date: 2026-09-11 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_competitor_research"
down_revision: str | None = "0003_knowledge_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

research_status_enum = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="research_status",
    create_type=False,
)


def upgrade() -> None:
    research_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "research_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
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
        sa.Column("query", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            research_status_enum,
            server_default=sa.text("'pending'::research_status"),
            nullable=False,
        ),
        sa.Column(
            "outline",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("title_hint", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "meta_description_hint",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column("url_slug_hint", sa.Text(), nullable=False, server_default=""),
        sa.Column("article_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
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
        "research_competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "headings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("image_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("video_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("list_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "has_faq",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "fetch_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["research_id"],
            ["research_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_competitors_research_id",
        "research_competitors",
        ["research_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_competitors_research_id",
        table_name="research_competitors",
    )
    op.drop_table("research_competitors")
    op.drop_table("research_runs")
    research_status_enum.drop(op.get_bind(), checkfirst=True)
