
"""Clean merge of all migration heads

Revision ID: clean_merge_final
Revises: 7fbece7d5bfd, remove_user_role_id, 16fc1ec782f4
Create Date: 2025-07-18 21:52:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'clean_merge_final'
down_revision = ('7fbece7d5bfd', 'remove_user_role_id', '16fc1ec782f4')
branch_labels = None
depends_on = None

def upgrade():
    # This is a merge migration - no operations needed
    pass

def downgrade():
    # This is a merge migration - no operations needed  
    pass
