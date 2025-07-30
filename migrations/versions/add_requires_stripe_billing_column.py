"""Add requires_stripe_billing column to subscription_tier

Revision ID: f8e9d7c6b5a4
Revises: 9a9557ebed61
Create Date: 2025-07-30 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8e9d7c6b5a4'
down_revision = '73e07c67ddb0'
branch_labels = None
depends_on = None


def upgrade():
    # Add the requires_stripe_billing column if it doesn't exist
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        try:
            batch_op.add_column(sa.Column('requires_stripe_billing', sa.Boolean(), nullable=True, default=True))
        except Exception:
            # Column might already exist, ignore the error
            pass


def downgrade():
    # Remove the requires_stripe_billing column
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        batch_op.drop_column('requires_stripe_billing')