
"""Add missing retention policy columns to subscription_tier

Revision ID: 20251009_1
Revises: 20251008_3
Create Date: 2025-10-09 18:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# Import the PostgreSQL helpers
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from postgres_helpers import (
    table_exists, column_exists, safe_add_column, safe_drop_column
)

revision = '20251009_1'
down_revision = '20251008_3'
branch_labels = None
depends_on = None


def upgrade():
    print("=== Adding missing retention policy columns to subscription_tier ===")
    
    if not table_exists('subscription_tier'):
        print("⚠️  subscription_tier table does not exist - skipping")
        return

    # Define all columns to add
    columns_to_add = [
        ('retention_policy', sa.String(16), False, 'one_year'),
        ('data_retention_days', sa.Integer, True, None),
        ('retention_notice_days', sa.Integer, True, None),
        ('storage_addon_retention_days', sa.Integer, True, None),
        ('tier_type', sa.String(32), False, 'monthly'),
        ('billing_provider', sa.String(32), False, 'exempt'),
        ('stripe_lookup_key', sa.String(128), True, None),
        ('stripe_storage_lookup_key', sa.String(128), True, None),
        ('whop_product_key', sa.String(128), True, None),
    ]

    success_count = 0
    
    for col_name, col_type, nullable, default in columns_to_add:
        if not column_exists('subscription_tier', col_name):
            try:
                if default:
                    column_def = sa.Column(col_name, col_type, nullable=nullable, server_default=default)
                else:
                    column_def = sa.Column(col_name, col_type, nullable=nullable)
                
                with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                    batch_op.add_column(column_def)
                
                print(f"   ✅ {col_name} column added successfully")
                success_count += 1
                
            except Exception as e:
                print(f"   ⚠️  Failed to add column {col_name}: {e}")
                # For PostgreSQL, we need to rollback and continue
                try:
                    op.get_bind().rollback()
                except:
                    pass
        else:
            print(f"   ℹ️  {col_name} column already exists - skipping")
            success_count += 1

    print(f"✅ Migration completed - {success_count}/{len(columns_to_add)} columns processed")


def downgrade():
    print("=== Removing retention policy columns from subscription_tier ===")
    
    if not table_exists('subscription_tier'):
        print("⚠️  subscription_tier table does not exist - skipping")
        return

    columns_to_remove = [
        'whop_product_key', 'stripe_storage_lookup_key', 'stripe_lookup_key',
        'billing_provider', 'tier_type', 'storage_addon_retention_days',
        'retention_notice_days', 'data_retention_days', 'retention_policy'
    ]

    for col_name in columns_to_remove:
        if column_exists('subscription_tier', col_name):
            try:
                with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                    batch_op.drop_column(col_name)
                print(f"   ✅ {col_name} column removed")
            except Exception as e:
                print(f"   ⚠️  Failed to remove column {col_name}: {e}")
                try:
                    op.get_bind().rollback()
                except:
                    pass

    print("✅ Downgrade completed")
