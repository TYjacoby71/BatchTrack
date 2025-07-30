
"""Add requires_stripe_billing column to subscription_tier

Revision ID: requires_stripe_billing
Revises: 73e07c67ddb0
Create Date: 2025-01-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'requires_stripe_billing'
down_revision = '73e07c67ddb0'
branch_labels = None
depends_on = None

def upgrade():
    # Add the requires_stripe_billing column with default True
    op.add_column('subscription_tier', sa.Column('requires_stripe_billing', sa.Boolean(), nullable=False, server_default='1'))
    
    # Update specific tiers to not require Stripe billing
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE subscription_tier SET requires_stripe_billing = 0 WHERE key IN ('exempt', 'free')")
    )

def downgrade():
    op.drop_column('subscription_tier', 'requires_stripe_billing')
