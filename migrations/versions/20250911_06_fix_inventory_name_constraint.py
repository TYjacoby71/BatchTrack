"""Fix inventory item name constraint to be organization-scoped

Revision ID: 20250911_06
Revises: 20250911_05
Create Date: 2025-09-11 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from postgres_helpers import ensure_unique_constraint_or_index, table_exists

# Helper functions to check for table and constraint existence
def _local_table_exists(table_name):
    # Kept for backward compatibility in this file; prefer helpers.table_exists
    return table_exists(table_name)

def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists on a table (portable)."""
    if not table_exists(table_name):
        return False
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        # Check foreign keys
        fks = inspector.get_foreign_keys(table_name)
        if any(fk.get('name') == constraint_name for fk in fks):
            return True
        # Check unique constraints if available
        try:
            uqs = inspector.get_unique_constraints(table_name)
            if any(uq.get('name') == constraint_name for uq in uqs):
                return True
        except Exception:
            pass
        # Fallback to information_schema on Postgres
        if bind.dialect.name in ("postgresql", "postgres"):
            result = bind.execute(text(
                """
                SELECT 1 
                FROM information_schema.table_constraints 
                WHERE table_name = :table_name 
                  AND constraint_name = :constraint_name
                """
            ), {"table_name": table_name, "constraint_name": constraint_name})
            return result.first() is not None
    except Exception:
        return False

def index_exists(table_name, index_name):
    """Check if an index exists on a table (portable)."""
    if not table_exists(table_name):
        return False
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        indexes = inspector.get_indexes(table_name)
        for idx in indexes:
            name = idx.get('name') or idx.get('indexname')
            if name == index_name:
                return True
        # Fallback per dialect
        if bind.dialect.name in ("postgresql", "postgres"):
            result = bind.execute(text(
                "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :n"
            ), {"t": table_name, "n": index_name})
            return result.first() is not None
        if bind.dialect.name == 'sqlite':
            result = bind.execute(text(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name = :n"
            ), {"n": index_name})
            return result.first() is not None
    except Exception:
        return False

# revision identifiers, used by Alembic.
revision = '20250911_06'
down_revision = '20250911_05'
branch_labels = None
depends_on = None

def upgrade():
    """Fix inventory item name constraints to be organization-scoped"""
    print("=== FIXING INVENTORY ITEM NAME CONSTRAINTS ===")

    if not table_exists('inventory_item'):
        print("⚠️ inventory_item table does not exist - skipping")
        return

    # 1. Try to drop the old global unique constraint if it exists
    print("1. Checking for old inventory_item_name_key constraint...")
    if constraint_exists('inventory_item', 'inventory_item_name_key'):
        try:
            print("   Dropping old inventory_item_name_key constraint...")
            op.drop_constraint('inventory_item_name_key', 'inventory_item', type_='unique')
            print("   ✅ Dropped global name constraint")
        except Exception as e:
            print(f"   ⚠️  Error dropping constraint: {e}")
    else:
        print("   ✅ Old constraint doesn't exist - skipping")

    # 2. Ensure proper organization+name unique constraint exists
    print("2. Checking for organization+name constraint...")
    created = ensure_unique_constraint_or_index('inventory_item', '_org_name_uc', ['organization_id', 'name'])
    if not created:
        print("   ✅ Organization+name unique already present")

    # 3. Ensure proper indexes exist
    print("3. Ensuring proper indexes...")

    # Name index
    if not index_exists('inventory_item', 'ix_inventory_item_name'):
        try:
            print("   Creating name index...")
            op.create_index('ix_inventory_item_name', 'inventory_item', ['name'])
            print("   ✅ Created name index")
        except Exception as e:
            print(f"   ⚠️  Error creating name index: {e}")
    else:
        print("   ✅ Name index already exists")

    # Organization ID index  
    if not index_exists('inventory_item', 'ix_inventory_item_organization_id'):
        try:
            print("   Creating organization_id index...")
            op.create_index('ix_inventory_item_organization_id', 'inventory_item', ['organization_id'])
            print("   ✅ Created organization_id index")
        except Exception as e:
            print(f"   ⚠️  Error creating organization_id index: {e}")
    else:
        print("   ✅ Organization_id index already exists")

    print("=== INVENTORY CONSTRAINT FIX COMPLETE ===")

def downgrade():
    """Revert inventory item name constraint changes"""
    print("=== REVERTING INVENTORY CONSTRAINT CHANGES ===")

    if not table_exists('inventory_item'):
        print("⚠️ inventory_item table does not exist - skipping downgrade")
        return

    if constraint_exists('inventory_item', '_org_name_uc'):
        try:
            op.drop_constraint('_org_name_uc', 'inventory_item', type_='unique')
            print("Dropped organization+name constraint")
        except Exception as e:
            print(f"⚠️  Error dropping constraint: {e}")

    if not constraint_exists('inventory_item', 'inventory_item_name_key'):
        try:
            op.create_unique_constraint('inventory_item_name_key', 'inventory_item', ['name'])
            print("Recreated global name constraint")
        except Exception as e:
            print(f"⚠️  Error recreating global constraint: {e}")

    print("=== INVENTORY CONSTRAINT REVERT COMPLETE ===")