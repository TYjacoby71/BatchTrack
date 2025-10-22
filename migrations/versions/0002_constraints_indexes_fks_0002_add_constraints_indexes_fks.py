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

    # Drop foreign key constraints safely (reverse order)
    if is_postgresql():
        # PostgreSQL can drop constraints by name
        try:
            op.drop_constraint("fk_product_sku_batch_id", "product_sku", type_="foreignkey")
        except Exception:
            pass
        try:
            op.drop_constraint("fk_batch_ingredient_batch_id", "batch_ingredient", type_="foreignkey")
        except Exception:
            pass  
        try:
            op.drop_constraint("fk_recipe_ingredient_recipe_id", "recipe_ingredient", type_="foreignkey")
        except Exception:
            pass
    # SQLite: constraints are embedded in table definitions, can't be dropped individually

    # Drop indexes safely
    safe_drop_index('ix_inventory_item_organization_id', 'inventory_item')
    safe_drop_index('ix_product_organization_id', 'product')  
    safe_drop_index('ix_batch_organization_id', 'batch')
    safe_drop_index('ix_recipe_organization_id', 'recipe')