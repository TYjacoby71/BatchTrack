
"""remove subscription tier from permissions

Revision ID: remove_subscription_tier_from_permissions
Revises: 
Create Date: 2025-07-23

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'remove_subscription_tier_from_permissions'
down_revision = '002_add_is_org_owner_nullable'
branch_labels = None
depends_on = None

def upgrade():
    # Remove the required_subscription_tier column from permission table
    with op.batch_alter_table('permission', schema=None) as batch_op:
        batch_op.drop_column('required_subscription_tier')

def downgrade():
    # Add the column back if we need to rollback
    with op.batch_alter_table('permission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('required_subscription_tier', sa.VARCHAR(length=32), nullable=True))
