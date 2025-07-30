
"""Add requires_stripe_billing column to subscription_tiers

Revision ID: a1b2c3d4e5f6
Revises: 9a9557ebed61
Create Date: 2025-07-30 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9a9557ebed61'
branch_labels = None
depends_on = None


def upgrade():
    # Add the requires_stripe_billing column with default True
    op.add_column('subscription_tiers', 
                  sa.Column('requires_stripe_billing', sa.Boolean(), 
                           nullable=False, server_default='1'))
    
    # Update specific tiers to not require billing
    op.execute("""
        UPDATE subscription_tiers 
        SET requires_stripe_billing = 0 
        WHERE tier_key IN ('exempt', 'free')
    """)


def downgrade():
    op.drop_column('subscription_tiers', 'requires_stripe_billing')
