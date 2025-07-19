
"""Add trial and billing fields to Organization

Revision ID: add_trial_billing
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'add_trial_billing'
down_revision = 'b2b4ce5f93fd'  # Replace with your latest migration
branch_labels = None
depends_on = None

def upgrade():
    # Add new columns to organization table
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trial_end_date', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('signup_source', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('promo_code', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('referral_code', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('billing_info', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('stripe_customer_id', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('subscription_status', sa.String(length=32), nullable=True, server_default='trial'))
        batch_op.add_column(sa.Column('next_billing_date', sa.DateTime(), nullable=True))

def downgrade():
    # Remove the columns
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.drop_column('next_billing_date')
        batch_op.drop_column('subscription_status')
        batch_op.drop_column('stripe_customer_id')
        batch_op.drop_column('billing_info')
        batch_op.drop_column('referral_code')
        batch_op.drop_column('promo_code')
        batch_op.drop_column('signup_source')
        batch_op.drop_column('trial_end_date')
