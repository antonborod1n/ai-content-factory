"""Step result payload on run_steps.

Revision ID: 0016_run_step_detail
Revises: 0015_runs
Create Date: 2026-11-11 12:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_run_step_detail"
down_revision: str | None = "0015_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "run_steps",
        sa.Column(
            "detail_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("run_steps", "detail_json")
