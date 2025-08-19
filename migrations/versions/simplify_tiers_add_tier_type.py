
"""simplify tiers add tier_type

Revision ID: simplify_tiers_add_tier_type
Revises: 758a11548815
Create Date: 2025-08-19 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'simplify_tiers_add_tier_type'
down_revision = '758a11548815'
branch_labels = None
depends_on = None


def upgrade():
    """Add tier_type column and make name unique, remove key column and is_billing_exempt"""
    
    connection = op.get_bind()
    
    # Add tier_type column
    op.add_column('subscription_tier', sa.Column('tier_type', sa.String(32), nullable=False, server_default='monthly'))
    
    # Make name unique (remove existing constraint on key first)
    try:
        connection.execute(text('DROP INDEX IF EXISTS uq_subscription_tier_key'))
        connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_tier_name ON subscription_tier(name)'))
    except Exception as e:
        print(f"Could not update constraints: {e}")
    
    # Remove key column if it exists
    try:
        connection.execute(text('ALTER TABLE subscription_tier DROP COLUMN key'))
    except Exception as e:
        print(f"Could not remove key column: {e}")
    
    # Remove is_billing_exempt column if it exists
    try:
        connection.execute(text('ALTER TABLE subscription_tier DROP COLUMN is_billing_exempt'))
    except Exception as e:
        print(f"Could not remove is_billing_exempt column: {e}")
    
    print("✅ Simplified subscription tier structure with tier_type")


def downgrade():
    """Restore key column and is_billing_exempt"""
    op.add_column('subscription_tier', sa.Column('key', sa.String(32), nullable=True))
    op.add_column('subscription_tier', sa.Column('is_billing_exempt', sa.Boolean, nullable=False, server_default='0'))
    
    # Generate keys from names for existing records
    connection = op.get_bind()
    connection.execute(text("UPDATE subscription_tier SET key = LOWER(REPLACE(REPLACE(name, ' Plan', ''), ' ', '_'))"))
    
    # Make key not nullable
    op.alter_column('subscription_tier', 'key', nullable=False)
