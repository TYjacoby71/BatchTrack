"""0002 add constraints/indexes/fks

Revision ID: 0002_constraints_indexes_fks
Revises: 0001_base_schema
Create Date: 2025-10-21 20:27:26.513838

"""
from alembic import op
import sqlalchemy as sa
from migrations.postgres_helpers import safe_create_foreign_key, is_sqlite


# revision identifiers, used by Alembic.
revision = '0002_constraints_indexes_fks'
down_revision = '0001_base_schema'
branch_labels = None
depends_on = None


def upgrade():
    # Add the deferred FKs to resolve cycle between batch <-> product_sku
    # Use safe helper to no-op on SQLite
    safe_create_foreign_key(
        "fk_batch_sku_id",
        "batch",
        "product_sku",
        ["sku_id"],
        ["id"],
    )
    
    # Add the reverse FK for product traceability to batch
    safe_create_foreign_key(
        "fk_product_sku_batch_id",
        "product_sku",
        "batch",
        ["batch_id"],
        ["id"],
    )


def downgrade():
    # Drop the deferred FKs added in this revision (skip on SQLite)
    if not is_sqlite():
        op.drop_constraint("fk_product_sku_batch_id", "product_sku", type_="foreignkey")
        op.drop_constraint("fk_batch_sku_id", "batch", type_="foreignkey")
