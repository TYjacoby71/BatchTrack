
"""Mock revision to fix migration chain

Revision ID: c4afe407ad19
Revises: 
Create Date: 2025-07-22 23:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4afe407ad19'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Mock migration - no actual schema changes
    # This migration exists to fix the migration chain
    pass


def downgrade():
    # Mock migration - no actual schema changes
    pass
