"""Add structural findings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column("finding_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("datasets", "finding_count", server_default=None)
    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.Uuid(),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("row", sa.Integer(), nullable=False),
        sa.Column("column", sa.String(255)),
        sa.Column("issue_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("original_value", postgresql.JSONB(), nullable=False),
        sa.Column("expected_value", postgresql.JSONB()),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("detector", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_findings_dataset_id", "findings", ["dataset_id"])


def downgrade() -> None:
    op.drop_table("findings")
    op.drop_column("datasets", "finding_count")
