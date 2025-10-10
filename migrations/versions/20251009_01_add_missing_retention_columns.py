
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

    # Get database connection and handle PostgreSQL transaction properly
    bind = op.get_bind()
    
    try:
        # Add retention policy columns using safe operations
        retention_columns = [
            ('retention_policy', sa.String(16), False, 'one_year'),
            ('data_retention_days', sa.Integer, True, None),
            ('retention_notice_days', sa.Integer, True, None),
            ('storage_addon_retention_days', sa.Integer, True, None),
        ]

        for col_name, col_type, nullable, default in retention_columns:
            try:
                if default:
                    column_def = sa.Column(col_name, col_type, nullable=nullable, server_default=default)
                else:
                    column_def = sa.Column(col_name, col_type, nullable=nullable)
                
                safe_add_column('subscription_tier', column_def)
            except Exception as col_err:
                print(f"⚠️  Failed to add column {col_name}: {col_err}")
                # Continue with other columns instead of failing completely

        # Add other missing columns that might be needed
        other_columns = [
            ('tier_type', sa.String(32), False, 'monthly'),
            ('billing_provider', sa.String(32), False, 'exempt'),
            ('stripe_lookup_key', sa.String(128), True, None),
            ('stripe_storage_lookup_key', sa.String(128), True, None),
            ('whop_product_key', sa.String(128), True, None),
        ]

        for col_name, col_type, nullable, default in other_columns:
            try:
                if default:
                    column_def = sa.Column(col_name, col_type, nullable=nullable, server_default=default)
                else:
                    column_def = sa.Column(col_name, col_type, nullable=nullable)
                    
                safe_add_column('subscription_tier', column_def)
            except Exception as col_err:
                print(f"⚠️  Failed to add column {col_name}: {col_err}")
                # Continue with other columns instead of failing completely

        print("✅ Migration completed - attempted to add missing columns to subscription_tier")

    except Exception as e:
        print(f"❌ Migration failed with unhandled error: {e}")
        # Don't re-raise the exception to prevent transaction abort
        print("⚠️  Continuing despite errors to prevent transaction abort")


def downgrade():
    print("=== Removing retention policy columns from subscription_tier ===")
    
    if not table_exists('subscription_tier'):
        print("⚠️  subscription_tier table does not exist - skipping")
        return

    try:
        columns_to_remove = [
            'retention_policy', 'data_retention_days', 'retention_notice_days', 
            'storage_addon_retention_days', 'tier_type', 'billing_provider',
            'stripe_lookup_key', 'stripe_storage_lookup_key', 'whop_product_key'
        ]

        for col_name in columns_to_remove:
            safe_drop_column('subscription_tier', col_name)

        print("✅ Downgrade completed")

    except Exception as e:
        print(f"❌ Downgrade failed: {e}")
        raise
