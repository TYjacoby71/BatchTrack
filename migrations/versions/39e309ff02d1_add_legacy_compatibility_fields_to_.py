"""add legacy compatibility fields to subscription tier

Revision ID: 39e309ff02d1
Revises: add_legacy_compatibility_fields
Create Date: 2025-08-11 23:25:44.567115

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '39e309ff02d1'
down_revision = 'add_legacy_compatibility_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Add legacy compatibility fields to subscription_tier table"""

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

    print("=== Adding legacy compatibility fields to subscription_tier ===")

    # Add stripe_product_id column if it doesn't exist
    if not column_exists('subscription_tier', 'stripe_product_id'):
        print("   Adding stripe_product_id column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('stripe_product_id', sa.String(128), nullable=True))
        print("✅ stripe_product_id column added successfully")
    else:
        print("   ⚠️  stripe_product_id column already exists, skipping")

    # Add stripe_price_id column if it doesn't exist
    if not column_exists('subscription_tier', 'stripe_price_id'):
        print("   Adding stripe_price_id column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('stripe_price_id', sa.String(128), nullable=True))
        print("✅ stripe_price_id column added successfully")
    else:
        print("   ⚠️  stripe_price_id column already exists, skipping")

    # Add stripe_price_id_monthly column if it doesn't exist  
    if not column_exists('subscription_tier', 'stripe_price_id_monthly'):
        print("   Adding stripe_price_id_monthly column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('stripe_price_id_monthly', sa.String(128), nullable=True))
        print("✅ stripe_price_id_monthly column added successfully")
    else:
        print("   ⚠️  stripe_price_id_monthly column already exists, skipping")

    # Add stripe_price_id_yearly column if it doesn't exist
    if not column_exists('subscription_tier', 'stripe_price_id_yearly'):
        print("   Adding stripe_price_id_yearly column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('stripe_price_id_yearly', sa.String(128), nullable=True))
        print("✅ stripe_price_id_yearly column added successfully")
    else:
        print("   ⚠️  stripe_price_id_yearly column already exists, skipping")

    print("=== Legacy compatibility fields migration completed ===")

def downgrade():
    """Remove legacy compatibility fields"""
    print("=== Removing legacy compatibility fields ===")

    # Helper function to check if column exists
    from sqlalchemy import inspect
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns

    # Remove the columns only if they exist
    columns_to_remove = ['stripe_price_id_yearly', 'stripe_price_id_monthly', 'stripe_price_id', 'whop_plan_id']
    existing_columns = []

    for col in columns_to_remove:
        if column_exists('subscription_tier', col):
            existing_columns.append(col)
            print(f"   Will remove column: {col}")
        else:
            print(f"   Column {col} does not exist - skipping")

    if existing_columns:
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            for col in existing_columns:
                batch_op.drop_column(col)
        print(f"   ✅ Removed {len(existing_columns)} columns")
    else:
        print("   ✅ No columns to remove")

    print("✅ Legacy compatibility fields removal completed")