
"""Add subscription tier table

Revision ID: add_subscription_tier_table
Revises: 47698e17fc63
Create Date: 2025-01-25 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_subscription_tier_table'
down_revision = '47698e17fc63'
branch_labels = None
depends_on = None

def upgrade():
    # Create subscription_tier table
    op.create_table('subscription_tier',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('key', sa.String(32), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('user_limit', sa.Integer(), default=1),
        sa.Column('is_customer_facing', sa.Boolean(), default=True),
        sa.Column('is_available', sa.Boolean(), default=True),
        sa.Column('stripe_lookup_key', sa.String(128), nullable=True),
        sa.Column('fallback_price_monthly', sa.String(32), default='$0'),
        sa.Column('fallback_price_yearly', sa.String(32), default='$0'),
        sa.Column('stripe_price_monthly', sa.String(32), nullable=True),
        sa.Column('stripe_price_yearly', sa.String(32), nullable=True),
        sa.Column('last_synced', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on key field
    op.create_index('idx_subscription_tier_key', 'subscription_tier', ['key'])
    
    # Add subscription_tier_id column to organization table
    op.add_column('organization', sa.Column('subscription_tier_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_organization_subscription_tier', 'organization', 'subscription_tier', ['subscription_tier_id'], ['id'])
    
    # Update subscription table to use tier_id instead of tier string
    op.add_column('subscription', sa.Column('tier_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_subscription_tier', 'subscription', 'subscription_tier', ['tier_id'], ['id'])

def downgrade():
    # Remove foreign keys and columns
    op.drop_constraint('fk_subscription_tier', 'subscription', type_='foreignkey')
    op.drop_column('subscription', 'tier_id')
    
    op.drop_constraint('fk_organization_subscription_tier', 'organization', type_='foreignkey')
    op.drop_column('organization', 'subscription_tier_id')
    
    # Drop subscription_tier table
    op.drop_index('idx_subscription_tier_key')
    op.drop_table('subscription_tier')
