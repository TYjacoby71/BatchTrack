
"""merge_multiple_heads

Revision ID: e9ef3d8c7df4
Revises: db37ade7bae5
Create Date: 2025-07-19 05:57:50.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9ef3d8c7df4'
down_revision = 'db37ade7bae5'
branch_labels = None
depends_on = None


def upgrade():
    # This is a mock migration to satisfy cached references
    # No actual schema changes needed
    pass


def downgrade():
    # This is a mock migration to satisfy cached references
    # No actual schema changes needed
    pass
