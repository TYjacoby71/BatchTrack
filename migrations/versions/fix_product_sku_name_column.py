
"""fix product_sku name column mismatch

Revision ID: fix_product_sku_name_column
Revises: c8f2e5a9b1d4
Create Date: 2025-08-08 04:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = 'fix_product_sku_name_column'
down_revision = 'c8f2e5a9b1d4'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    """Fix product_sku name/sku_name column mismatch"""
    print("=== Fixing product_sku name/sku_name column mismatch ===")
    
    if not table_exists('product_sku'):
        print("   product_sku table does not exist - skipping")
        return
    
    bind = op.get_bind()
    
    # Check what columns exist
    has_name = column_exists('product_sku', 'name')
    has_sku_name = column_exists('product_sku', 'sku_name')
    
    print(f"   name column exists: {has_name}")
    print(f"   sku_name column exists: {has_sku_name}")
    
    if has_name and not has_sku_name:
        # Rename name to sku_name
        print("   Renaming 'name' column to 'sku_name'")
        
        # First ensure no NULL values
        try:
            bind.execute(text("""
                UPDATE product_sku 
                SET name = COALESCE(NULLIF(name, ''), sku_code, 'Unnamed SKU') 
                WHERE name IS NULL OR name = ''
            """))
        except Exception as e:
            print(f"   Warning: Could not update NULL names: {e}")
        
        # Rename the column (works for both PostgreSQL and SQLite)
        try:
            op.alter_column('product_sku', 'name', new_column_name='sku_name')
            print("   ✅ Successfully renamed name to sku_name")
        except Exception as e:
            print(f"   ❌ Could not rename column: {e}")
            
    elif has_name and has_sku_name:
        # Both exist - copy name to sku_name where sku_name is NULL, then drop name
        print("   Both columns exist - migrating data and dropping 'name'")
        
        try:
            bind.execute(text("""
                UPDATE product_sku 
                SET sku_name = COALESCE(NULLIF(sku_name, ''), NULLIF(name, ''), sku_code, 'Unnamed SKU')
                WHERE sku_name IS NULL OR sku_name = ''
            """))
            print("   ✅ Migrated name data to sku_name")
            
            # Drop the old name column
            op.drop_column('product_sku', 'name')
            print("   ✅ Dropped old 'name' column")
            
        except Exception as e:
            print(f"   ❌ Could not migrate data: {e}")
            
    elif not has_name and has_sku_name:
        print("   ✅ Already correct - only sku_name column exists")
        
    else:
        # Neither exists - this shouldn't happen but let's add sku_name
        print("   Adding missing sku_name column")
        op.add_column('product_sku', sa.Column('sku_name', sa.String(128), nullable=True))
        
        # Set default values
        try:
            bind.execute(text("""
                UPDATE product_sku 
                SET sku_name = COALESCE(sku_code, 'Unnamed SKU')
                WHERE sku_name IS NULL
            """))
        except Exception as e:
            print(f"   Warning: Could not set default sku_name values: {e}")


def downgrade():
    """Rename sku_name back to name"""
    if table_exists('product_sku') and column_exists('product_sku', 'sku_name'):
        op.alter_column('product_sku', 'sku_name', new_column_name='name')
