
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
            batch_op.add_column(sa.Column('max_users', sa.Integer, nullable=False, default=1))
        print("✅ max_users column added successfully")
    else:
        print("   ⚠️  max_users column already exists, skipping")
    
    # Add max_monthly_batches column if it doesn't exist
    if not column_exists('subscription_tier', 'max_monthly_batches'):
        print("   Adding max_monthly_batches column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('max_monthly_batches', sa.Integer, nullable=False, default=0))
        print("✅ max_monthly_batches column added successfully")
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
    """Remove the added columns"""
    print("=== Removing tier_key and related columns ===")
    
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        # Drop unique constraint first
        try:
            batch_op.drop_constraint('uq_subscription_tier_tier_key', type_='unique')
        except Exception:
            pass
        
        # Drop columns
        batch_op.drop_column('max_monthly_batches')
        batch_op.drop_column('max_users')
        batch_op.drop_column('tier_key')
    
    print("✅ Downgrade completed")
