
"""restore missing timestamp columns

Revision ID: restore_timestamps
Revises: fix_nullable_constraints
Create Date: 2025-02-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = 'restore_timestamps'
down_revision = 'fix_nullable_constraints'
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
    print("=== Restoring missing timestamp columns ===")
    
    # Add missing updated_at column to ingredient_category table
    if table_exists('ingredient_category'):
        if not column_exists('ingredient_category', 'updated_at'):
            print("Adding updated_at column to ingredient_category...")
            op.add_column('ingredient_category', sa.Column('updated_at', sa.DateTime(), nullable=True))
        
        if not column_exists('ingredient_category', 'created_at'):
            print("Adding created_at column to ingredient_category...")
            op.add_column('ingredient_category', sa.Column('created_at', sa.DateTime(), nullable=True))

    # Add missing timestamp columns to other tables that inherit from TimestampMixin
    tables_needing_timestamps = [
        'inventory_item',
        'batch',
        'product',
        'recipe',
        'unit',
        'tag',
        'permission'
    ]

    for table_name in tables_needing_timestamps:
        if table_exists(table_name):
            if not column_exists(table_name, 'created_at'):
                print(f"Adding created_at column to {table_name}...")
                op.add_column(table_name, sa.Column('created_at', sa.DateTime(), nullable=True))
            
            if not column_exists(table_name, 'updated_at'):
                print(f"Adding updated_at column to {table_name}...")
                op.add_column(table_name, sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Set default values for newly added timestamp columns
    bind = op.get_bind()
    current_timestamp = "datetime('now')"
    
    for table_name in ['ingredient_category'] + tables_needing_timestamps:
        if table_exists(table_name):
            if column_exists(table_name, 'created_at'):
                print(f"Setting default created_at values for {table_name}...")
                bind.execute(text(f'UPDATE {table_name} SET created_at = {current_timestamp} WHERE created_at IS NULL'))
            
            if column_exists(table_name, 'updated_at'):
                print(f"Setting default updated_at values for {table_name}...")
                bind.execute(text(f'UPDATE {table_name} SET updated_at = {current_timestamp} WHERE updated_at IS NULL'))

    print("✅ Migration completed: Restored missing timestamp columns")


def downgrade():
    print("=== Removing restored timestamp columns ===")
    
    # Remove timestamp columns from ingredient_category
    if table_exists('ingredient_category'):
        if column_exists('ingredient_category', 'updated_at'):
            op.drop_column('ingredient_category', 'updated_at')
        if column_exists('ingredient_category', 'created_at'):
            op.drop_column('ingredient_category', 'created_at')

    # Remove timestamp columns from other tables
    tables_needing_timestamps = [
        'inventory_item',
        'batch',
        'product',
        'recipe',
        'unit',
        'tag',
        'permission'
    ]

    for table_name in tables_needing_timestamps:
        if table_exists(table_name):
            if column_exists(table_name, 'updated_at'):
                op.drop_column(table_name, 'updated_at')
            if column_exists(table_name, 'created_at'):
                op.drop_column(table_name, 'created_at')

    print("✅ Downgrade completed: Removed timestamp columns")
