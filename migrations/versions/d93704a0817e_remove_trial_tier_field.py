
"""remove_trial_tier_field

Revision ID: d93704a0817e
Revises: remove_organization_timezone
Create Date: 2025-07-21 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd93704a0817e'
down_revision = 'remove_organization_timezone'
branch_labels = None
depends_on = None


def upgrade():
    # Mock migration - no actual changes needed
    pass


def downgrade():
    # Mock migration - no actual changes needed
    pass
