
"""Add billing and pricing snapshots for resilience

Revision ID: add_billing_resilience_tables
Revises: 
Create Date: 2025-07-24 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'add_billing_resilience_tables'
down_revision = None  # Replace with latest revision
branch_labels = None
depends_on = None


def upgrade():
    # Create billing_snapshots table
    op.create_table('billing_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('confirmed_tier', sa.String(length=32), nullable=False),
        sa.Column('confirmed_status', sa.String(length=32), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=128), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=128), nullable=True),
        sa.Column('grace_period_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_stripe_sync', sa.DateTime(), nullable=False),
        sa.Column('sync_source', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create pricing_snapshots table
    op.create_table('pricing_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stripe_price_id', sa.String(length=128), nullable=False),
        sa.Column('stripe_lookup_key', sa.String(length=64), nullable=False),
        sa.Column('stripe_product_id', sa.String(length=128), nullable=False),
        sa.Column('unit_amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('interval', sa.String(length=16), nullable=False),
        sa.Column('interval_count', sa.Integer(), nullable=True),
        sa.Column('product_name', sa.String(length=128), nullable=False),
        sa.Column('product_description', sa.Text(), nullable=True),
        sa.Column('features', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_stripe_sync', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_price_id')
    )


def downgrade():
    op.drop_table('pricing_snapshots')
    op.drop_table('billing_snapshots')
