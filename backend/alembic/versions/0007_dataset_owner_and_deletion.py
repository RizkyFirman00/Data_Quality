"""Scope assessments to their uploader and retain recoverable deletion."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("datasets", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column("datasets", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_datasets_owner", "datasets", "local_users", ["owner_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_datasets_owner_id", "datasets", ["owner_id"])
    op.create_index("ix_datasets_deleted_at", "datasets", ["deleted_at"])


def downgrade():
    op.drop_index("ix_datasets_deleted_at", table_name="datasets")
    op.drop_index("ix_datasets_owner_id", table_name="datasets")
    op.drop_constraint("fk_datasets_owner", "datasets", type_="foreignkey")
    op.drop_column("datasets", "deleted_at")
    op.drop_column("datasets", "owner_id")
