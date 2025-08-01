
"""add missing created_at and updated_at columns to all models

Revision ID: add_missing_created_at_columns
Revises: add_unit_timestamps
Create Date: 2025-02-01 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_missing_created_at_columns'
down_revision = 'add_unit_timestamps'
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


def add_timestamp_columns(table_name):
    """Add created_at and updated_at columns to a table if they don't exist"""
    if not table_exists(table_name):
        print(f"   ⚠️  Table '{table_name}' doesn't exist, skipping")
        return 0
    
    print(f"   Checking table: {table_name}")
    columns_added = 0
    
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if not column_exists(table_name, 'created_at'):
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
            columns_added += 1
            print(f"      ✅ Added created_at column")
        else:
            print(f"      ℹ️  created_at column already exists")
            
        if not column_exists(table_name, 'updated_at'):
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
            columns_added += 1
            print(f"      ✅ Added updated_at column")
        else:
            print(f"      ℹ️  updated_at column already exists")
    
    if columns_added == 0:
        print(f"      ✅ Table '{table_name}' timestamp columns up to date")
    
    return columns_added


def upgrade():
    """Add missing timestamp columns to all relevant tables"""
    print("=== Adding missing timestamp columns to all models ===")
    
    # List of tables that should have timestamp columns based on models that use TimestampMixin
    tables_needing_timestamps = [
        'batch',
        'billing_snapshot',
        'ingredient_category',  # Actually this one was removed from model
        'inventory_item',
        'permission',
        'pricing_snapshot',
        'product',
        'product_sku',
        'product_sku_history',
        'product_variant',
        'recipe',
        'recipe_ingredient',
        'reservation',
        'role',
        'statistics',
        'subscription_tier',
        'user_role_assignment',
        'developer_role',
        'organization',
        'user',
        'custom_unit_mapping',
        'conversion_log',
        'tag'
    ]
    
    total_columns_added = 0
    
    for table_name in tables_needing_timestamps:
        # Skip ingredient_category since it was intentionally removed from the model
        if table_name == 'ingredient_category':
            print(f"   ⚠️  Skipping '{table_name}' - timestamps intentionally excluded")
            continue
            
        columns_added = add_timestamp_columns(table_name)
        total_columns_added += columns_added
    
    print(f"✅ Migration completed: Added {total_columns_added} timestamp columns across all tables")
    print("⚠️  All timestamp columns added as nullable for safety")


def downgrade():
    """Remove timestamp columns (only the ones we added)"""
    print("=== Removing timestamp columns added by this migration ===")
    
    tables_to_revert = [
        'batch',
        'billing_snapshot',
        'inventory_item', 
        'permission',
        'pricing_snapshot',
        'product',
        'product_sku',
        'product_sku_history',
        'product_variant',
        'recipe',
        'recipe_ingredient',
        'reservation',
        'role',
        'statistics',
        'subscription_tier',
        'user_role_assignment',
        'developer_role',
        'organization',
        'user',
        'custom_unit_mapping',
        'conversion_log',
        'tag'
    ]
    
    for table_name in tables_to_revert:
        if table_exists(table_name):
            print(f"   Reverting table: {table_name}")
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                if column_exists(table_name, 'updated_at'):
                    batch_op.drop_column('updated_at')
                    print(f"      ✅ Removed updated_at column")
                if column_exists(table_name, 'created_at'):
                    batch_op.drop_column('created_at')
                    print(f"      ✅ Removed created_at column")
    
    print("✅ Downgrade completed")
