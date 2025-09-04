
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


def table_exists(table_name):
    """Check if a table exists in the database"""
    try:
        inspector = inspect(op.get_bind())
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def upgrade():
    print("Creating inventory_category table and adding inventory_category_id column...")
    
    # 1. First, create the inventory_category table if it doesn't exist
    if not table_exists('inventory_category'):
        try:
            print("   Creating inventory_category table...")
            op.create_table('inventory_category',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('name', sa.String(64), nullable=False),
                sa.Column('description', sa.Text(), nullable=True),
                sa.Column('item_type', sa.String(32), nullable=False),
                sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
                sa.Column('created_by', sa.Integer(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True),
                sa.Column('organization_id', sa.Integer(), nullable=True),
                sa.PrimaryKeyConstraint('id'),
                sa.ForeignKeyConstraint(['created_by'], ['user.id']),
                sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
                sa.UniqueConstraint('name', 'item_type', 'organization_id', name='_invcat_name_type_org_uc')
            )
            print("   ✅ Created inventory_category table")
        except Exception as e:
            print(f"   ⚠️  Error creating inventory_category table: {e}")
    else:
        print("   ℹ️  Table inventory_category already exists")
    
    # 2. Now add the column to inventory_item if it doesn't exist
    if not column_exists('inventory_item', 'inventory_category_id'):
        try:
            print("   Adding inventory_category_id column to inventory_item...")
            op.add_column('inventory_item', 
                sa.Column('inventory_category_id', sa.Integer(), nullable=True))
            print("   ✅ Added inventory_category_id column")
        except Exception as e:
            print(f"   ⚠️  Error adding column: {e}")
    else:
        print("   ℹ️  Column inventory_category_id already exists")
        
    # 3. Add the foreign key constraint
    try:
        print("   Adding foreign key constraint...")
        op.create_foreign_key(
            'fk_inventory_item_inventory_category',
            'inventory_item', 
            'inventory_category', 
            ['inventory_category_id'], 
            ['id']
        )
        print("   ✅ Added foreign key constraint")
    except Exception as e:
        print(f"   ⚠️  Error adding foreign key constraint (may already exist): {e}")
            
    # 4. Add index for the foreign key
    try:
        print("   Adding index for inventory_category_id...")
        op.create_index('ix_inventory_item_inventory_category_id', 
                      'inventory_item', ['inventory_category_id'])
        print("   ✅ Created inventory_category_id index")
    except Exception as e:
        print(f"   ⚠️  Error creating index (may already exist): {e}")
    
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
