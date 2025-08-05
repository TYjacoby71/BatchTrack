
"""Add Whop integration fields to SubscriptionTier

Revision ID: add_whop_tier_fields
Revises: whop_integration
Create Date: 2024-01-15 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_whop_tier_fields'
down_revision = 'whop_integration'
branch_labels = None
depends_on = None

def upgrade():
    # Add Whop integration fields to subscription_tier table
    op.add_column('subscription_tier', sa.Column('whop_product_key', sa.String(128), nullable=True))
    op.add_column('subscription_tier', sa.Column('whop_product_name', sa.String(256), nullable=True))
    op.add_column('subscription_tier', sa.Column('whop_last_synced', sa.DateTime(), nullable=True))
    op.add_column('subscription_tier', sa.Column('requires_whop_billing', sa.Boolean(), default=False))

def downgrade():
    # Remove Whop integration fields
    op.drop_column('subscription_tier', 'requires_whop_billing')
    op.drop_column('subscription_tier', 'whop_last_synced')
    op.drop_column('subscription_tier', 'whop_product_name')
    op.drop_column('subscription_tier', 'whop_product_key')
