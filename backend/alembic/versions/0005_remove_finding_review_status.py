"""Remove finding review status and audit workflow.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS finding_audits")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_status")
    op.drop_column("findings", "status")


def downgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
    )
    op.create_check_constraint(
        "ck_findings_status",
        "findings",
        "status IN ('OPEN', 'REVIEWED', 'ACCEPTED', 'DISMISSED')",
    )
    op.create_table(
        "finding_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "finding_id",
            sa.Uuid(),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_status", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reviewer", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_finding_audits_finding_id", "finding_audits", ["finding_id"])
