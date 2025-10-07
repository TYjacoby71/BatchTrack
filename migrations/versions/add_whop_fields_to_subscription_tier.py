"""Add Whop integration fields to SubscriptionTier

Revision ID: a1b2c3d4e5f6789012345678901234ab
Revises: whop_integration
Create Date: 2024-10-07 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6789012345678901234ab'
down_revision = 'whop_integration'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    try:
        connection = op.get_bind()
        inspector = inspect(connection)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade():
    """Add Whop integration fields to subscription_tier table"""
    print("=== Adding Whop integration fields to SubscriptionTier ===")

    # Add whop_product_key column if it doesn't exist
    if not column_exists('subscription_tier', 'whop_product_key'):
        op.add_column('subscription_tier', sa.Column('whop_product_key', sa.String(128), nullable=True))
        print("   ✅ Added whop_product_key column")
    else:
        print("   ⚠️  whop_product_key column already exists, skipping...")

    # Add whop_plan_name column if it doesn't exist
    if not column_exists('subscription_tier', 'whop_plan_name'):
        op.add_column('subscription_tier', sa.Column('whop_plan_name', sa.String(128), nullable=True))
        print("   ✅ Added whop_plan_name column")
    else:
        print("   ⚠️  whop_plan_name column already exists, skipping...")

    # Add whop_enabled column if it doesn't exist
    if not column_exists('subscription_tier', 'whop_enabled'):
        op.add_column('subscription_tier', sa.Column('whop_enabled', sa.Boolean(), nullable=True, default=False))
        print("   ✅ Added whop_enabled column")
    else:
        print("   ⚠️  whop_enabled column already exists, skipping...")

    print("   ✅ Migration completed successfully")


def downgrade():
    """Remove Whop integration fields from subscription_tier table"""
    print("=== Removing Whop integration fields from SubscriptionTier ===")

    # Remove columns if they exist
    if column_exists('subscription_tier', 'whop_enabled'):
        op.drop_column('subscription_tier', 'whop_enabled')
        print("   ✅ Removed whop_enabled column")

    if column_exists('subscription_tier', 'whop_plan_name'):
        op.drop_column('subscription_tier', 'whop_plan_name')
        print("   ✅ Removed whop_plan_name column")

    if column_exists('subscription_tier', 'whop_product_key'):
        op.drop_column('subscription_tier', 'whop_product_key')
        print("   ✅ Removed whop_product_key column")

    print("   ✅ Rollback completed successfully")