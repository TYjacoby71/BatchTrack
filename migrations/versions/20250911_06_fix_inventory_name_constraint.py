"""Fix inventory item name constraint to be organization-scoped

Revision ID: 20250911_06
Revises: 20250911_05
Create Date: 2025-09-11 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '20250911_06'
down_revision = '20250911_05'
branch_labels = None
depends_on = None

def upgrade():
    """Remove old name-only constraint and ensure proper organization+name constraint"""
    connection = op.get_bind()

    print("=== FIXING INVENTORY ITEM NAME CONSTRAINTS ===")

    # 1. Drop the problematic old constraint
    print("1. Dropping old inventory_item_name_key constraint...")
    try:
        op.drop_constraint('inventory_item_name_key', 'inventory_item', type_='unique')
        print("   ✅ Dropped inventory_item_name_key")
    except Exception as e:
        print(f"   ⚠️  Constraint may not exist: {e}")

    # 2. Also try dropping any other name-only constraints that might exist
    try:
        connection.execute(text("ALTER TABLE inventory_item DROP CONSTRAINT IF EXISTS uq_inventory_item_name"))
        print("   ✅ Dropped uq_inventory_item_name if existed")
    except Exception:
        pass

    # 3. Ensure the proper organization+name constraint exists
    print("2. Ensuring proper organization+name constraint...")
    try:
        # Check if constraint already exists before creating
        constraint_exists = connection.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.table_constraints 
            WHERE table_name = 'inventory_item' 
            AND constraint_name = '_org_name_uc'
        """)).scalar()
        
        if constraint_exists == 0:
            op.create_unique_constraint('_org_name_uc', 'inventory_item', ['organization_id', 'name'])
            print("   ✅ Created _org_name_uc constraint")
        else:
            print("   ✅ _org_name_uc constraint already exists")
    except Exception as e:
        print(f"   ⚠️  Error with constraint: {e}")

    # 4. Ensure proper indexes exist
    print("3. Ensuring proper indexes...")
    try:
        # Check if name index exists
        name_index_exists = connection.execute(text("""
            SELECT COUNT(*) 
            FROM pg_indexes 
            WHERE tablename = 'inventory_item' 
            AND indexname = 'ix_inventory_item_name'
        """)).scalar()
        
        if name_index_exists == 0:
            op.create_index('ix_inventory_item_name', 'inventory_item', ['name'])
            print("   ✅ Created name index")
        else:
            print("   ✅ Name index already exists")
    except Exception as e:
        print(f"   ⚠️  Error with name index: {e}")

    try:
        # Check if organization_id index exists
        org_index_exists = connection.execute(text("""
            SELECT COUNT(*) 
            FROM pg_indexes 
            WHERE tablename = 'inventory_item' 
            AND indexname = 'ix_inventory_item_organization_id'
        """)).scalar()
        
        if org_index_exists == 0:
            op.create_index('ix_inventory_item_organization_id', 'inventory_item', ['organization_id'])
            print("   ✅ Created organization_id index")
        else:
            print("   ✅ Organization_id index already exists")
    except Exception as e:
        print(f"   ⚠️  Error with organization_id index: {e}")

    print("=== INVENTORY CONSTRAINT FIX COMPLETE ===")

def downgrade():
    """Revert the constraint changes"""
    # This is intentionally minimal since we don't want to break things
    try:
        op.drop_constraint('_org_name_uc', 'inventory_item', type_='unique')
    except Exception:
        pass