"""create articles table

Revision ID: 0001_create_articles
Revises:
Create Date: 2026-09-06 17:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_create_articles"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

article_status_enum = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="article_status",
    create_type=False,
)


def upgrade() -> None:
    article_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "articles",
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
        sa.Column(
            "keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            article_status_enum,
            server_default=sa.text("'pending'::article_status"),
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


def downgrade() -> None:
    op.drop_table("articles")
    article_status_enum.drop(op.get_bind(), checkfirst=True)
