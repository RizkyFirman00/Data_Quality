"""Add reviewer workflow and reassessment metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("source_metadata", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("datasets", sa.Column("assessment_status", sa.String(32)))
    op.add_column("datasets", sa.Column("parent_dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id", ondelete="SET NULL")))
    op.create_check_constraint(
        "ck_datasets_assessment_status",
        "datasets",
        "assessment_status IS NULL OR assessment_status IN ('PASSED', 'NEEDS_CORRECTION')",
    )
    op.create_check_constraint(
        "ck_findings_status",
        "findings",
        "status IN ('OPEN', 'REVIEWED', 'ACCEPTED', 'DISMISSED')",
    )
    op.create_index("ix_datasets_parent_dataset_id", "datasets", ["parent_dataset_id"])
    op.alter_column("datasets", "source_metadata", server_default=None)
    op.create_table(
        "finding_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("finding_id", sa.Uuid(), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reviewer", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_finding_audits_finding_id", "finding_audits", ["finding_id"])


def downgrade() -> None:
    op.drop_table("finding_audits")
    op.drop_index("ix_datasets_parent_dataset_id", table_name="datasets")
    op.drop_constraint("ck_findings_status", "findings", type_="check")
    op.drop_constraint("ck_datasets_assessment_status", "datasets", type_="check")
    op.drop_column("datasets", "parent_dataset_id")
    op.drop_column("datasets", "assessment_status")
    op.drop_column("datasets", "source_metadata")
