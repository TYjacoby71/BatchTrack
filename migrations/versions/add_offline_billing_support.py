
"""Add offline billing support

Revision ID: add_offline_billing_support
Revises: drop_deprecated_billing_columns
Create Date: 2025-08-06 05:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_offline_billing_support'
down_revision = 'drop_deprecated_billing_columns'
branch_labels = None
depends_on = None

def upgrade():
    # Add offline support to subscription_tier
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_billing_sync', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('grace_period_days', sa.Integer(), default=7))

    # Add offline support to organization  
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_online_sync', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('offline_tier_cache', sa.JSON(), nullable=True))

def downgrade():
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.drop_column('offline_tier_cache')
        batch_op.drop_column('last_online_sync')
        
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        batch_op.drop_column('grace_period_days')
        batch_op.drop_column('last_billing_sync')
