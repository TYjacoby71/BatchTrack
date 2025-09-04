
"""
Add missing inventory_category_id column to inventory_item table

Revision ID: 20250904_04
Revises: 20250904_03
Create Date: 2025-09-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20250904_04'
down_revision = '20250904_03'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    try:
        inspector = inspect(op.get_bind())
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade():
    print("Adding missing inventory_category_id column to inventory_item...")
    
    # Check if column already exists
    if not column_exists('inventory_item', 'inventory_category_id'):
        try:
            op.add_column('inventory_item', 
                sa.Column('inventory_category_id', sa.Integer(), 
                         sa.ForeignKey('inventory_category.id'), nullable=True))
            print("   ✅ Added inventory_category_id column")
        except Exception as e:
            print(f"   ⚠️  Error adding column: {e}")
            
        # Add index for the foreign key
        try:
            op.create_index('ix_inventory_item_inventory_category_id', 
                          'inventory_item', ['inventory_category_id'])
            print("   ✅ Created inventory_category_id index")
        except Exception as e:
            print(f"   ⚠️  Error creating index: {e}")
    else:
        print("   ℹ️  Column inventory_category_id already exists")
    
    print("✅ Migration completed")


def downgrade():
    print("Removing inventory_category_id column...")
    try:
        op.drop_index('ix_inventory_item_inventory_category_id', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_column('inventory_item', 'inventory_category_id')
    except Exception:
        pass
    print("✅ Rollback completed")
