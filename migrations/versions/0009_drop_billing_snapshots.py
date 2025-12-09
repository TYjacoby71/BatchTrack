"""0009 drop billing snapshots

Revision ID: 0009_drop_billing_snapshots
Revises: 0008_pending_signup
Create Date: 2025-11-18 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import table_exists


# revision identifiers, used by Alembic.
revision = '0009_drop_billing_snapshots'
down_revision = '0008_pending_signup'
branch_labels = None
depends_on = None


def upgrade():
    if table_exists('billing_snapshots'):
        op.drop_table('billing_snapshots')


def downgrade():
    # Downgrade recreates the table structure without data.
    op.create_table(
        'billing_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('confirmed_tier', sa.String(length=32), nullable=False),
        sa.Column('confirmed_status', sa.String(length=32), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=128)),
        sa.Column('stripe_customer_id', sa.String(length=128)),
        sa.Column('grace_period_days', sa.Integer(), server_default='3'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_stripe_sync', sa.DateTime(), nullable=False),
        sa.Column('sync_source', sa.String(length=64)),
    )
