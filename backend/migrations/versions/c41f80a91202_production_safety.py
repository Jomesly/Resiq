"""Recoverable workspaces and durable image cleanup."""

import sqlalchemy as sa
from alembic import op

revision = "c41f80a91202"
down_revision = "b20ae57b5016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("workspaces", sa.Column("recovery_hash", sa.String(64), nullable=True))
    op.add_column("workspaces", sa.Column("pending_recovery_hash", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_workspaces_recovery_hash", "workspaces", ["recovery_hash"])
    op.create_table(
        "blob_cleanup",
        sa.Column("prefix", sa.Text(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade():
    op.drop_table("blob_cleanup")
    op.drop_constraint("uq_workspaces_recovery_hash", "workspaces", type_="unique")
    op.drop_column("workspaces", "pending_recovery_hash")
    op.drop_column("workspaces", "recovery_hash")
