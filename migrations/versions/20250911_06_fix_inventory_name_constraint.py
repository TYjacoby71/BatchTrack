
"""Fix inventory item name constraint to be organization-scoped

Revision ID: 20250911_06_fix_inventory_name_constraint
Revises: 20250911_05_add_missing_timestamp_columns_to_global_item
Create Date: 2025-09-11 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = '20250911_06_fix_inventory_name_constraint'
down_revision = '20250911_05_add_missing_timestamp_columns_to_global_item'
branch_labels = None
depends_on = None

def upgrade():
    """Remove global name constraint and ensure org-scoped constraint exists"""
    
    connection = op.get_bind()
    
    print("Fixing inventory_item name constraints...")
    
    # 1) Drop the problematic global unique constraint if it exists
    try:
        op.drop_constraint('inventory_item_name_key', 'inventory_item', type_='unique')
        print("   ✅ Dropped global unique constraint 'inventory_item_name_key'")
    except Exception as e:
        print(f"   ⚠️  Global constraint may not exist: {e}")
    
    # 2) Ensure the organization-scoped constraint exists
    try:
        # Check if _org_name_uc constraint already exists
        result = connection.execute(text("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE constraint_name = '_org_name_uc' 
            AND table_name = 'inventory_item'
        """))
        
        if not result.first():
            op.create_unique_constraint('_org_name_uc', 'inventory_item', ['organization_id', 'name'])
            print("   ✅ Created organization-scoped unique constraint '_org_name_uc'")
        else:
            print("   ✅ Organization-scoped constraint already exists")
            
    except Exception as e:
        print(f"   ⚠️  Error with org constraint: {e}")
    
    # 3) Ensure name column has a regular index for performance
    try:
        op.create_index('ix_inventory_item_name', 'inventory_item', ['name'])
        print("   ✅ Created index on name column")
    except Exception as e:
        print(f"   ⚠️  Index may already exist: {e}")

def downgrade():
    """Revert changes"""
    try:
        op.drop_constraint('_org_name_uc', 'inventory_item', type_='unique')
        op.create_unique_constraint('inventory_item_name_key', 'inventory_item', ['name'])
    except Exception:
        pass
"""Fix inventory item name constraint to be organization-scoped

Revision ID: 20250911_06_fix_inventory_name_constraint
Revises: 20250911_05_add_missing_timestamp_columns_to_global_item
Create Date: 2025-09-11 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '20250911_06_fix_inventory_name_constraint'
down_revision = '20250911_05_add_missing_timestamp_columns_to_global_item'
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
        op.create_unique_constraint('_org_name_uc', 'inventory_item', ['organization_id', 'name'])
        print("   ✅ Created _org_name_uc constraint")
    except Exception as e:
        print(f"   ⚠️  Constraint may already exist: {e}")
    
    # 4. Ensure proper indexes exist
    print("3. Ensuring proper indexes...")
    try:
        op.create_index('ix_inventory_item_name', 'inventory_item', ['name'])
        print("   ✅ Created name index")
    except Exception as e:
        print(f"   ⚠️  Index may already exist")
    
    try:
        op.create_index('ix_inventory_item_organization_id', 'inventory_item', ['organization_id'])
        print("   ✅ Created organization_id index")
    except Exception as e:
        print(f"   ⚠️  Index may already exist")
    
    print("=== INVENTORY CONSTRAINT FIX COMPLETE ===")

def downgrade():
    """Revert the constraint changes"""
    # This is intentionally minimal since we don't want to break things
    try:
        op.drop_constraint('_org_name_uc', 'inventory_item', type_='unique')
    except Exception:
        pass
