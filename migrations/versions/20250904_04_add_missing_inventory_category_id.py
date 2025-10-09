
"""Add missing inventory_category_id column to inventory_item table

Revision ID: 20250904_04
Revises: 20250904_03
Create Date: 2025-09-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20250904_04'
down_revision = '20250904_03'
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

def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        constraints = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return constraint_name in constraints
    except Exception:
        return False

def index_exists(table_name, index_name):
    """Check if an index exists"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False

def upgrade():
    """Add missing inventory_category_id column to inventory_item table"""
    print("Creating inventory_category table and adding inventory_category_id column...")
    
    # Create inventory_category table if it doesn't exist
    if not table_exists('inventory_category'):
        print("   Creating inventory_category table...")
        op.create_table('inventory_category',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('is_global_category', sa.Boolean(), default=False),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )
        print("   ✅ Created inventory_category table")
    else:
        print("   ℹ️  Table inventory_category already exists")
    
    # Add inventory_category_id column if it doesn't exist
    if not column_exists('inventory_item', 'inventory_category_id'):
        print("   Adding inventory_category_id column...")
        op.add_column('inventory_item', sa.Column('inventory_category_id', sa.Integer(), nullable=True))
        print("   ✅ Added inventory_category_id column")
    else:
        print("   ℹ️  Column inventory_category_id already exists")
    
    # Add foreign key constraint if it doesn't exist
    if not constraint_exists('inventory_item', 'fk_inventory_item_inventory_category'):
        print("   Adding foreign key constraint...")
        try:
            op.create_foreign_key(
                'fk_inventory_item_inventory_category',
                'inventory_item',
                'inventory_category',
                ['inventory_category_id'],
                ['id']
            )
            print("   ✅ Added foreign key constraint")
        except Exception as e:
            print(f"   ⚠️  Could not add foreign key constraint: {e}")
    else:
        print("   ✅ Foreign key constraint already exists")
    
    # Add index if it doesn't exist
    if not index_exists('inventory_item', 'ix_inventory_item_inventory_category_id'):
        print("   Adding index for inventory_category_id...")
        try:
            op.create_index(
                'ix_inventory_item_inventory_category_id',
                'inventory_item',
                ['inventory_category_id']
            )
            print("   ✅ Added index for inventory_category_id")
        except Exception as e:
            print(f"   ⚠️  Could not add index: {e}")
    else:
        print("   ✅ Index already exists")
    
    print("✅ Migration completed")

def downgrade():
    """Remove the inventory_category_id column and related constraints"""
    print("Removing inventory_category_id column and related constraints...")
    
    # Drop index if it exists
    if index_exists('inventory_item', 'ix_inventory_item_inventory_category_id'):
        try:
            op.drop_index('ix_inventory_item_inventory_category_id', 'inventory_item')
            print("   ✅ Dropped index")
        except Exception as e:
            print(f"   ⚠️  Could not drop index: {e}")
    
    # Drop foreign key constraint if it exists
    if constraint_exists('inventory_item', 'fk_inventory_item_inventory_category'):
        try:
            op.drop_constraint('fk_inventory_item_inventory_category', 'inventory_item', type_='foreignkey')
            print("   ✅ Dropped foreign key constraint")
        except Exception as e:
            print(f"   ⚠️  Could not drop foreign key constraint: {e}")
    
    # Drop column if it exists
    if column_exists('inventory_item', 'inventory_category_id'):
        try:
            op.drop_column('inventory_item', 'inventory_category_id')
            print("   ✅ Dropped inventory_category_id column")
        except Exception as e:
            print(f"   ⚠️  Could not drop column: {e}")
    
    print("✅ Downgrade completed")
