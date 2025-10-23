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
    # Add deferred foreign keys that would create circular dependencies in 0001

    # Add the batch.sku_id → product_sku.id FK
    with op.batch_alter_table('batch', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_batch_sku_id', 'product_sku', ['sku_id'], ['id'])

    # Add the deferred FKs to resolve cycle between batch <-> product_sku
    # Use safe helper to no-op on SQLite and handle existing constraints
    from migrations.postgres_helpers import is_postgresql
    from sqlalchemy import text

    if is_postgresql():
        bind = op.get_bind()

        # Check if fk_batch_sku_id already exists
        result = bind.execute(text("""
            SELECT COUNT(*) FROM information_schema.table_constraints 
            WHERE constraint_name = 'fk_batch_sku_id' 
            AND table_name = 'batch'
        """))
        if result.scalar() == 0:
            safe_create_foreign_key(
                "fk_batch_sku_id",
                "batch", 
                "product_sku",
                ["sku_id"],
                ["id"],
            )

        # Check if fk_product_sku_batch_id already exists  
        result = bind.execute(text("""
            SELECT COUNT(*) FROM information_schema.table_constraints 
            WHERE constraint_name = 'fk_product_sku_batch_id' 
            AND table_name = 'product_sku'
        """))
        if result.scalar() == 0:
            safe_create_foreign_key(
                "fk_product_sku_batch_id",
                "product_sku",
                "batch", 
                ["batch_id"],
                ["id"],
            )
    else:
        # SQLite - no-op as intended
        pass


def downgrade():
    # Safe downgrade that handles transaction issues
    from migrations.postgres_helpers import safe_drop_foreign_key, is_postgresql

    if is_postgresql():
        # Safely drop foreign keys we created, with proper transaction handling
        bind = op.get_bind()
        
        # Drop in reverse order of creation
        constraints_to_drop = [
            ("fk_product_sku_batch_id", "product_sku"),
            ("fk_batch_sku_id", "batch")
        ]
        
        for constraint_name, table_name in constraints_to_drop:
            try:
                # Check if constraint exists before trying to drop it
                result = bind.execute(sa.text("""
                    SELECT COUNT(*) FROM information_schema.table_constraints 
                    WHERE constraint_name = :c AND table_name = :t
                """), {"c": constraint_name, "t": table_name})
                
                if result.scalar() > 0:
                    op.drop_constraint(constraint_name, table_name, type_="foreignkey")
                    print(f"✅ Dropped constraint {constraint_name}")
            except Exception as e:
                print(f"⚠️ Could not drop constraint {constraint_name}: {e}")
                # Continue with other operations
                pass
    
    # SQLite: No foreign keys to drop since upgrade() is no-op on SQLite