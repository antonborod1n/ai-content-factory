"""Composite indexes for per-project list queries.

Revision ID: 0017_list_indexes
Revises: 0016_run_step_detail
Create Date: 2026-11-11 16:05:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_list_indexes"
down_revision: str | None = "0016_run_step_detail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = (
    ("ix_articles_project_created_at", "articles", ["project_id", "created_at"]),
    ("ix_articles_project_status", "articles", ["project_id", "status"]),
    ("ix_documents_project_created_at", "documents", ["project_id", "created_at"]),
    (
        "ix_content_plans_project_created_at",
        "content_plans",
        ["project_id", "created_at"],
    ),
    (
        "ix_research_runs_project_created_at",
        "research_runs",
        ["project_id", "created_at"],
    ),
)


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
