"""Merge migration heads

Revision ID: a9764225f9aa
Revises: add_organization_settings, add_required_subscription_tier
Create Date: 2025-07-18 01:26:36.492261

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9764225f9aa'
down_revision = ('add_organization_settings', 'add_required_subscription_tier')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
