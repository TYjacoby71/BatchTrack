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
    from migrations.postgres_helpers import safe_drop_foreign_key, safe_drop_index, is_postgresql
    
    # Safe downgrade - only drop what we actually created in upgrade()
    # The upgrade() only creates two foreign keys, so only drop those
    
    if is_postgresql():
        # Drop the foreign keys we created in upgrade() (in reverse order)
        try:
            op.drop_constraint("fk_product_sku_batch_id", "product_sku", type_="foreignkey")
        except Exception:
            # Constraint might not exist, continue
            pass
            
        try:
            op.drop_constraint("fk_batch_sku_id", "batch", type_="foreignkey")  
        except Exception:
            # Constraint might not exist, continue
            pass
    
    # SQLite: No foreign keys to drop since upgrade() is no-op on SQLite