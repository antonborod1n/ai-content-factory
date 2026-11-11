"""projects table and project_id on isolated entities

Revision ID: 0014_projects
Revises: 0013_article_review
Create Date: 2026-09-24 04:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_projects"
down_revision: str | None = "0013_article_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_ID = "00000000-0000-4000-8000-000000000001"
_TABLES = ("articles", "documents", "research_runs", "content_plans")


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column(
            "language",
            sa.String(length=10),
            nullable=False,
            server_default="ru",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
    )
    op.execute(
        "INSERT INTO projects (id, slug, name, language) "
        f"VALUES ('{_DEFAULT_ID}', 'default', 'Default', 'ru')"
    )
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "project_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.execute(
            f"UPDATE {table} SET project_id = '{_DEFAULT_ID}' "
            "WHERE project_id IS NULL"
        )
        op.alter_column(table, "project_id", nullable=False)
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])
        op.create_foreign_key(
            f"fk_{table}_project_id",
            table,
            "projects",
            ["project_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_constraint(f"fk_{table}_project_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        op.drop_column(table, "project_id")
    op.drop_table("projects")
