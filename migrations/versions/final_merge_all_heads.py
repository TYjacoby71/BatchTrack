
"""Final merge of all migration heads

Revision ID: final_merge_all_heads
Revises: 32aaf310779c, 47eadd04f263
Create Date: 2025-07-18 01:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'final_merge_all_heads'
down_revision = ('32aaf310779c', '47eadd04f263')
branch_labels = None
depends_on = None

def upgrade():
    # This is a merge migration - no operations needed
    pass

def downgrade():
    # This is a merge migration - no operations needed
    pass
