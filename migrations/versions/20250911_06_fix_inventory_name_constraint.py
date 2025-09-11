
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
