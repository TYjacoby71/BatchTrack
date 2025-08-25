"""add tier_key column to subscription_tier

Revision ID: add_tier_key_column
Revises: add_unique_constraint_stripe
Create Date: 2025-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'add_tier_key_column'
down_revision = 'add_unique_constraint_stripe'
branch_labels = None
depends_on = None

def upgrade():
    """Add missing tier_key column and other missing fields to subscription_tier table"""

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

    print("=== Adding missing columns to subscription_tier ===")

    # Add tier_key column if it doesn't exist
    if not column_exists('subscription_tier', 'tier_key'):
        print("   Adding tier_key column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('tier_key', sa.String(64), nullable=True, index=True))
        print("✅ tier_key column added successfully")
    else:
        print("   ⚠️  tier_key column already exists, skipping")

    # Add max_users column if it doesn't exist  
    if not column_exists('subscription_tier', 'max_users'):
        print("   Adding max_users column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('max_users', sa.Integer, nullable=True))
        print("✅ max_users column added successfully")

        # Update existing records with default value
        print("   Setting default values for max_users...")
        connection.execute(sa.text("UPDATE subscription_tier SET max_users = 1 WHERE max_users IS NULL"))

        # Make column NOT NULL after setting values
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.alter_column('max_users', nullable=False)
    else:
        print("   ⚠️  max_users column already exists, skipping")

    # Add max_monthly_batches column if it doesn't exist
    if not column_exists('subscription_tier', 'max_monthly_batches'):
        print("   Adding max_monthly_batches column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('max_monthly_batches', sa.Integer, nullable=True))
        print("✅ max_monthly_batches column added successfully")

        # Update existing records with default value
        print("   Setting default values for max_monthly_batches...")
        connection.execute(sa.text("UPDATE subscription_tier SET max_monthly_batches = 0 WHERE max_monthly_batches IS NULL"))

        # Make column NOT NULL after setting values
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.alter_column('max_monthly_batches', nullable=False)
    else:
        print("   ⚠️  max_monthly_batches column already exists, skipping")

    # Populate tier_key with key values for existing records
    print("   Populating tier_key values from key column...")
    connection.execute(sa.text("""
        UPDATE subscription_tier 
        SET tier_key = key 
        WHERE tier_key IS NULL AND key IS NOT NULL
    """))

    # Make tier_key not nullable and unique after populating
    if column_exists('subscription_tier', 'tier_key'):
        print("   Making tier_key not nullable and unique...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.alter_column('tier_key', nullable=False)
            # Add unique constraint
            try:
                batch_op.create_unique_constraint('uq_subscription_tier_tier_key', ['tier_key'])
            except Exception as e:
                print(f"   ⚠️  Could not add unique constraint (may already exist): {e}")

    print("=== Migration completed ===")

def downgrade():
    """Remove tier_key and related columns"""
    print("=== Removing tier_key and related columns ===")

    # Helper function to check if constraint exists
    from sqlalchemy import inspect
    connection = op.get_bind()
    inspector = inspect(connection)

    def constraint_exists(table_name, constraint_name):
        try:
            constraints = inspector.get_unique_constraints(table_name)
            return any(c['name'] == constraint_name for c in constraints)
        except Exception:
            return False

    def column_exists(table_name, column_name):
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns

    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        # Drop the unique constraint only if it exists
        if constraint_exists('subscription_tier', 'uq_subscription_tier_tier_key'):
            batch_op.drop_constraint('uq_subscription_tier_tier_key', type_='unique')
            print("   ✅ Dropped constraint uq_subscription_tier_tier_key")
        else:
            print("   ℹ️  Constraint uq_subscription_tier_tier_key does not exist - skipping")

        # Drop the tier_key column only if it exists
        if column_exists('subscription_tier', 'tier_key'):
            batch_op.drop_column('tier_key')
            print("   ✅ Dropped column tier_key")
        else:
            print("   ℹ️  Column tier_key does not exist - skipping")

    print("✅ tier_key column and constraints removal completed")