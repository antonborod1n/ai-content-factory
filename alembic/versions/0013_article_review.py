"""add articles.review_status for operator review

Revision ID: 0013_article_review
Revises: 0012_competitor_topics
Create Date: 2026-09-24 04:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_article_review"
down_revision: str | None = "0012_competitor_topics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    review_status = sa.Enum(
        "pending",
        "approved",
        "rejected",
        name="review_status",
    )
    review_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "articles",
        sa.Column(
            "review_status",
            review_status,
            nullable=False,
            server_default="pending",
        ),
    )


def downgrade() -> None:
    op.drop_column("articles", "review_status")
    sa.Enum(name="review_status").drop(op.get_bind(), checkfirst=True)
