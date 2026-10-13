"""Persist grouped AI action summaries with each finding.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("action_summary", sa.Text()))
    op.add_column("findings", sa.Column("action_summary_source", sa.String(16)))
    op.add_column("findings", sa.Column("action_summary_confidence", sa.Float()))


def downgrade() -> None:
    op.drop_column("findings", "action_summary_confidence")
    op.drop_column("findings", "action_summary_source")
    op.drop_column("findings", "action_summary")
