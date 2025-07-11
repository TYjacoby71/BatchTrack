
"""Mock revision for missing reference

Revision ID: 0e1482a435f4
Revises: aa271449bf33
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0e1482a435f4'
down_revision = 'aa271449bf33'
branch_labels = None
depends_on = None

def upgrade():
    # This is a mock revision - no actual changes needed
    pass

def downgrade():
    # This is a mock revision - no actual changes needed
    pass
