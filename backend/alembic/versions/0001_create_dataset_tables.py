"""Create dataset tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "PROCESSING", "COMPLETED", "FAILED", name="datasetstatus", create_type=False
    )
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("file_type", sa.String(8), nullable=False),
        sa.Column("worksheet_name", sa.String(255)),
        sa.Column("original_file_key", sa.String(500)),
        sa.Column("snapshot_key", sa.String(500)),
        sa.Column("status", status, nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_row_count", sa.Integer(), nullable=False),
        sa.Column("preview", postgresql.JSONB(), nullable=False),
        sa.Column("failure_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "column_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("inferred_type", sa.String(32), nullable=False),
        sa.Column("candidate_role", sa.String(32), nullable=False),
        sa.Column("null_count", sa.Integer(), nullable=False),
        sa.Column("empty_count", sa.Integer(), nullable=False),
        sa.Column("unique_count", sa.Integer(), nullable=False),
        sa.Column("sample_values", postgresql.JSONB(), nullable=False),
        sa.Column("distribution", postgresql.JSONB()),
    )
    op.create_index("ix_column_profiles_dataset_id", "column_profiles", ["dataset_id"])


def downgrade() -> None:
    op.drop_table("column_profiles")
    op.drop_table("datasets")
    sa.Enum(name="datasetstatus").drop(op.get_bind(), checkfirst=True)
