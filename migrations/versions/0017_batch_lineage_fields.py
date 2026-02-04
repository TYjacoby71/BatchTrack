"""Add batch lineage tracking fields."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_batch_lineage_fields"
down_revision = "0016_recipe_lineage_system"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("batch", sa.Column("target_version_id", sa.Integer(), nullable=True))
    op.add_column("batch", sa.Column("lineage_id", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        "fk_batch_target_version_id",
        "batch",
        "recipe",
        ["target_version_id"],
        ["id"],
    )
    op.create_index("ix_batch_target_version_id", "batch", ["target_version_id"], unique=False)
    op.create_index("ix_batch_lineage_id", "batch", ["lineage_id"], unique=False)

    op.add_column("inventory_history", sa.Column("lineage_id", sa.String(length=64), nullable=True))
    op.add_column("unified_inventory_history", sa.Column("lineage_id", sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column("unified_inventory_history", "lineage_id")
    op.drop_column("inventory_history", "lineage_id")

    op.drop_index("ix_batch_lineage_id", table_name="batch")
    op.drop_index("ix_batch_target_version_id", table_name="batch")
    op.drop_constraint("fk_batch_target_version_id", "batch", type_="foreignkey")
    op.drop_column("batch", "lineage_id")
    op.drop_column("batch", "target_version_id")
