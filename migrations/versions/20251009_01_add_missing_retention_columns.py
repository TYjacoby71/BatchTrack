
"""Add missing retention policy columns to subscription_tier

Revision ID: 20251009_1
Revises: 20251008_3
Create Date: 2025-10-09 18:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20251009_1'
down_revision = '20251008_3'
branch_labels = None
depends_on = None


def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    print("=== Adding missing retention policy columns to subscription_tier ===")
    
    if not table_exists('subscription_tier'):
        print("⚠️  subscription_tier table does not exist - skipping")
        return

    # Add retention policy columns
    retention_columns = [
        ('retention_policy', sa.String(16), False, 'one_year'),
        ('data_retention_days', sa.Integer, True, None),
        ('retention_notice_days', sa.Integer, True, None),
        ('storage_addon_retention_days', sa.Integer, True, None),
    ]

    for col_name, col_type, nullable, default in retention_columns:
        if not column_exists('subscription_tier', col_name):
            print(f"   Adding {col_name} column...")
            if default:
                op.add_column('subscription_tier', sa.Column(col_name, col_type, nullable=nullable, server_default=default))
            else:
                op.add_column('subscription_tier', sa.Column(col_name, col_type, nullable=nullable))
            print(f"   ✅ {col_name} column added")
        else:
            print(f"   ⚠️  {col_name} column already exists")

    # Add other missing columns that might be needed
    other_columns = [
        ('tier_type', sa.String(32), False, 'monthly'),
        ('billing_provider', sa.String(32), False, 'exempt'),
        ('stripe_lookup_key', sa.String(128), True, None),
        ('stripe_storage_lookup_key', sa.String(128), True, None),
        ('whop_product_key', sa.String(128), True, None),
    ]

    for col_name, col_type, nullable, default in other_columns:
        if not column_exists('subscription_tier', col_name):
            print(f"   Adding {col_name} column...")
            if default:
                op.add_column('subscription_tier', sa.Column(col_name, col_type, nullable=nullable, server_default=default))
            else:
                op.add_column('subscription_tier', sa.Column(col_name, col_type, nullable=nullable))
            print(f"   ✅ {col_name} column added")
        else:
            print(f"   ⚠️  {col_name} column already exists")

    print("✅ Migration completed - missing columns added to subscription_tier")


def downgrade():
    print("=== Removing retention policy columns from subscription_tier ===")
    
    columns_to_remove = [
        'retention_policy', 'data_retention_days', 'retention_notice_days', 
        'storage_addon_retention_days', 'tier_type', 'billing_provider',
        'stripe_lookup_key', 'stripe_storage_lookup_key', 'whop_product_key'
    ]

    for col_name in columns_to_remove:
        if column_exists('subscription_tier', col_name):
            try:
                op.drop_column('subscription_tier', col_name)
                print(f"   ✅ Removed {col_name} column")
            except Exception as e:
                print(f"   ⚠️  Could not remove {col_name}: {e}")
        else:
            print(f"   ⚠️  {col_name} column does not exist")
