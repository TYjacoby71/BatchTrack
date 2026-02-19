"""Add item-level quantity tracking flag for infinite inventory mode.

Synopsis:
Adds inventory_item.is_tracked so stock checks and deductions can treat items
as infinite without removing recipe/batch workflows.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import safe_add_column, safe_drop_column, column_exists


revision = "0025_inventory_item_is_tracked"
down_revision = "0024_saop_c_indexes"
branch_labels = None
depends_on = None


def upgrade():
    safe_add_column(
        "inventory_item",
        sa.Column("is_tracked", sa.Boolean(), nullable=True, server_default=sa.true()),
        verbose=False,
    )

    if column_exists("inventory_item", "is_tracked"):
        op.execute("UPDATE inventory_item SET is_tracked = TRUE WHERE is_tracked IS NULL")
        with op.batch_alter_table("inventory_item") as batch_op:
            batch_op.alter_column("is_tracked", nullable=False, server_default=sa.true())


def downgrade():
    safe_drop_column("inventory_item", "is_tracked", verbose=False)
