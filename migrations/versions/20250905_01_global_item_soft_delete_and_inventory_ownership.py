
"""Add soft-delete fields to global_item and ownership to inventory_item

Revision ID: 20250905_01
Revises: 20250904_04a
Create Date: 2025-09-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20250905_01'
down_revision = '20250904_04a'
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


def index_exists(table_name, index_name):
    """Check if an index exists"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    print("Starting global_item soft-delete and inventory_item ownership migration...")
    
    # GlobalItem soft-delete columns
    if table_exists('global_item'):
        print("Adding soft-delete columns to global_item...")
        
        if not column_exists('global_item', 'is_archived'):
            print("  Adding is_archived column...")
            op.add_column('global_item', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        else:
            print("  is_archived column already exists")
            
        if not column_exists('global_item', 'archived_at'):
            print("  Adding archived_at column...")
            op.add_column('global_item', sa.Column('archived_at', sa.DateTime(), nullable=True))
        else:
            print("  archived_at column already exists")
            
        if not column_exists('global_item', 'archived_by'):
            print("  Adding archived_by column...")
            op.add_column('global_item', sa.Column('archived_by', sa.Integer(), nullable=True))
        else:
            print("  archived_by column already exists")
            
        if not index_exists('global_item', 'ix_global_item_is_archived'):
            print("  Creating index on is_archived...")
            op.create_index('ix_global_item_is_archived', 'global_item', ['is_archived'])
        else:
            print("  Index ix_global_item_is_archived already exists")
    else:
        print("  global_item table does not exist, skipping...")

    # InventoryItem ownership column
    if table_exists('inventory_item'):
        print("Adding ownership column to inventory_item...")
        
        if not column_exists('inventory_item', 'ownership'):
            print("  Adding ownership column...")
            op.add_column('inventory_item', sa.Column('ownership', sa.String(length=16), nullable=True))
        else:
            print("  ownership column already exists")
            
        if not index_exists('inventory_item', 'ix_inventory_item_ownership'):
            print("  Creating index on ownership...")
            op.create_index('ix_inventory_item_ownership', 'inventory_item', ['ownership'])
        else:
            print("  Index ix_inventory_item_ownership already exists")

        # Backfill ownership where possible
        print("  Backfilling ownership values...")
        bind = op.get_bind()
        result = bind.execute(sa.text("SELECT COUNT(*) FROM inventory_item WHERE ownership IS NULL")).scalar()
        if result > 0:
            print(f"    Found {result} inventory items without ownership, backfilling...")
            bind.execute(sa.text("""
                UPDATE inventory_item 
                SET ownership = CASE 
                    WHEN global_item_id IS NOT NULL THEN 'global' 
                    ELSE 'org' 
                END 
                WHERE ownership IS NULL
            """))
            print(f"    Backfilled {result} inventory items")
        else:
            print("    All inventory items already have ownership values")
    else:
        print("  inventory_item table does not exist, skipping...")

    print("✅ Migration completed successfully!")


def downgrade():
    print("Reversing global_item soft-delete and inventory_item ownership migration...")
    
    # Drop inventory_item changes
    if table_exists('inventory_item'):
        print("Removing ownership changes from inventory_item...")
        
        if index_exists('inventory_item', 'ix_inventory_item_ownership'):
            print("  Dropping ownership index...")
            op.drop_index('ix_inventory_item_ownership', table_name='inventory_item')
            
        if column_exists('inventory_item', 'ownership'):
            print("  Dropping ownership column...")
            op.drop_column('inventory_item', 'ownership')

    # Drop global_item changes
    if table_exists('global_item'):
        print("Removing soft-delete changes from global_item...")
        
        if index_exists('global_item', 'ix_global_item_is_archived'):
            print("  Dropping is_archived index...")
            op.drop_index('ix_global_item_is_archived', table_name='global_item')
            
        if column_exists('global_item', 'archived_by'):
            print("  Dropping archived_by column...")
            op.drop_column('global_item', 'archived_by')
            
        if column_exists('global_item', 'archived_at'):
            print("  Dropping archived_at column...")
            op.drop_column('global_item', 'archived_at')
            
        if column_exists('global_item', 'is_archived'):
            print("  Dropping is_archived column...")
            op.drop_column('global_item', 'is_archived')

    print("✅ Downgrade completed successfully!")
