
"""Add required_subscription_tier to permissions

Revision ID: add_required_tier
Revises: fb4c629d09cc
Create Date: 2025-07-24 18:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_required_tier'
down_revision = 'fb4c629d09cc'
branch_labels = None
depends_on = None


def upgrade():
    # Add required_subscription_tier column to permission table
    op.add_column('permission', sa.Column('required_subscription_tier', sa.String(32), nullable=True))
    
    # Set default value for existing permissions
    op.execute("UPDATE permission SET required_subscription_tier = 'free' WHERE required_subscription_tier IS NULL")
    
    # Make the column non-nullable after setting defaults
    op.alter_column('permission', 'required_subscription_tier', nullable=False)


def downgrade():
    # Remove required_subscription_tier column
    op.drop_column('permission', 'required_subscription_tier')
