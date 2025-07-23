"""remove_subscription_tier_from_permissions

Revision ID: fb4c629d09cc
Revises: 002_add_is_org_owner_nullable
Create Date: 2025-07-23 21:12:24.788887

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fb4c629d09cc'
down_revision = '002_add_is_org_owner_nullable'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
