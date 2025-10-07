
"""Add Whop integration fields to SubscriptionTier

Revision ID: a1b2c3d4e5f6789012345678901234ab
Revises: whop_integration
Create Date: 2024-01-15 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a1b2c3d4e5f6789012345678901234ab'
down_revision = 'whop_integration'
branch_labels = None
depends_on = None

def upgrade():
    """Add Whop integration fields to SubscriptionTier"""
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    print("=== Adding Whop integration fields to SubscriptionTier ===")

    # Add Whop integration columns only if they don't exist
    whop_columns = [
        ('whop_product_key', sa.String(128)),
        ('whop_product_name', sa.String(256)),
        ('whop_last_synced', sa.DateTime()),
        ('requires_whop_billing', sa.Boolean())
    ]

    for col_name, col_type in whop_columns:
        if not column_exists('subscription_tier', col_name):
            print(f"   Adding {col_name} column...")
            if col_name == 'requires_whop_billing':
                op.add_column('subscription_tier', sa.Column(col_name, col_type, default=False, server_default='false'))
            else:
                op.add_column('subscription_tier', sa.Column(col_name, col_type, nullable=True))
            print(f"   ✅ Added {col_name}")
        else:
            print(f"   ⚠️  {col_name} column already exists, skipping")

    print("✅ Whop integration fields migration completed")

def downgrade():
    """Remove Whop integration fields from SubscriptionTier"""
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    print("=== Removing Whop integration fields from SubscriptionTier ===")

    whop_columns = ['requires_whop_billing', 'whop_last_synced', 'whop_product_name', 'whop_product_key']

    for col_name in whop_columns:
        if column_exists('subscription_tier', col_name):
            print(f"   Removing {col_name} column...")
            op.drop_column('subscription_tier', col_name)
            print(f"   ✅ Removed {col_name}")
        else:
            print(f"   ⚠️  {col_name} column does not exist, skipping")

    print("✅ Whop integration fields downgrade completed")
