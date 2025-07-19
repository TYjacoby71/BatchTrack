"""Add required_subscription_tier column to permission table

Revision ID: add_required_subscription_tier
Revises: fix_developer_users
Create Date: 2025-01-17 20:25:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_required_subscription_tier'
down_revision = 'fix_developer_users'
branch_labels = None
depends_on = None

def upgrade():
    # Add required_subscription_tier column to permission table
    with op.batch_alter_table('permission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('required_subscription_tier', sa.String(length=32), nullable=True, default='free'))

    # Update existing permissions to have default tier
    op.execute("UPDATE permission SET required_subscription_tier = 'free' WHERE required_subscription_tier IS NULL")

def downgrade():
    # Remove required_subscription_tier column from permission table
    with op.batch_alter_table('permission', schema=None) as batch_op:
        batch_op.drop_column('required_subscription_tier')