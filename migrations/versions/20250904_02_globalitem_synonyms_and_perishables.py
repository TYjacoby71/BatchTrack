"""Extend GlobalItem with synonyms and perishable defaults

Revision ID: 20250904_02
Revises: 20250904_01a
Create Date: 2025-08-27 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20250904_02'
down_revision = '20250904_01a'
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
    """Add synonyms and perishable defaults to global_item"""
    print("=== Adding synonyms and perishable defaults to global_item ===")

    # Add aka_names column if it doesn't exist
    add_column_if_not_exists('global_item', 'aka_names', sa.JSON(), nullable=True)

    # Add default_is_perishable column if it doesn't exist
    add_column_if_not_exists('global_item', 'default_is_perishable', sa.Boolean(), nullable=True)

    # Add default_days_until_expiration column if it doesn't exist
    add_column_if_not_exists('global_item', 'default_days_until_expiration', sa.Integer(), nullable=True)

    print("✅ GlobalItem synonyms and perishables migration completed")

def downgrade():
    """Remove the added columns"""
    print("=== Removing synonyms and perishable defaults from global_item ===")

    # Remove columns only if they exist
    drop_column_if_exists('global_item', 'default_days_until_expiration')
    drop_column_if_exists('global_item', 'default_is_perishable')
    drop_column_if_exists('global_item', 'aka_names')

    print("✅ GlobalItem synonyms and perishables downgrade completed")