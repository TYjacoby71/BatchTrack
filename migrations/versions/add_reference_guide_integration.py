
"""Add reference guide integration fields

Revision ID: add_reference_guide_integration
Revises: add_capacity_fields
Create Date: 2025-08-27 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'add_reference_guide_integration'
down_revision = 'add_capacity_fields'
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
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def add_column_if_not_exists(table_name, column_name, column_type, **kwargs):
    """Add a column only if it doesn't already exist"""
    if not column_exists(table_name, column_name):
        print(f"   Adding {column_name} column to {table_name}...")
        op.add_column(table_name, sa.Column(column_name, column_type, **kwargs))
        print(f"   ✅ Added {column_name} column to {table_name}")
        return True
    else:
        print(f"   ✅ {column_name} column already exists in {table_name}")
        return False

def drop_column_if_exists(table_name, column_name):
    """Drop a column only if it exists"""
    if column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)
        print(f"   ✅ Dropped {column_name} column from {table_name}")
        return True
    else:
        print(f"   ℹ️  {column_name} column does not exist in {table_name}")
        return False

def upgrade():
    """Add reference guide integration fields"""
    print("=== Adding reference guide integration fields ===")
    
    # Add reference_item_name column to inventory_item if it doesn't exist
    add_column_if_not_exists('inventory_item', 'reference_item_name', sa.String(128), nullable=True)
    
    # Add reference_item_type column to inventory_item if it doesn't exist
    add_column_if_not_exists('inventory_item', 'reference_item_type', sa.String(64), nullable=True)
    
    # Add reference_guide_url column to inventory_item if it doesn't exist
    add_column_if_not_exists('inventory_item', 'reference_guide_url', sa.Text(), nullable=True)
    
    print("✅ Reference guide integration migration completed")

def downgrade():
    """Remove reference guide integration fields"""
    print("=== Removing reference guide integration fields ===")
    
    # Remove columns only if they exist
    drop_column_if_exists('inventory_item', 'reference_guide_url')
    drop_column_if_exists('inventory_item', 'reference_item_type')
    drop_column_if_exists('inventory_item', 'reference_item_name')
    
    print("✅ Reference guide integration downgrade completed")
