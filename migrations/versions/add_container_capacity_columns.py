
"""Add container capacity columns

Revision ID: add_capacity_fields
Revises: add_comprehensive_stats
Create Date: 2025-08-27 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'add_capacity_fields'
down_revision = 'add_comprehensive_stats'
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
    """Add container capacity columns"""
    print("=== Adding container capacity columns ===")
    
    # Add capacity column to inventory_item if it doesn't exist
    add_column_if_not_exists('inventory_item', 'capacity', sa.Float(), nullable=True)
    
    # Add capacity_unit column to inventory_item if it doesn't exist
    add_column_if_not_exists('inventory_item', 'capacity_unit', sa.String(50), nullable=True)
    
    print("✅ Container capacity columns migration completed")

def downgrade():
    """Remove container capacity columns"""
    print("=== Removing container capacity columns ===")
    
    # Remove columns only if they exist
    drop_column_if_exists('inventory_item', 'capacity_unit')
    drop_column_if_exists('inventory_item', 'capacity')
    
    print("✅ Container capacity columns downgrade completed")
