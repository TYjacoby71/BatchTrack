
"""Final head merge 2025

Revision ID: final_head_merge_2025
Revises: zzz_final_consolidation, 7fbece7d5bfd, merge_all_heads_final
Create Date: 2025-07-19 04:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'final_head_merge_2025'
down_revision = ('zzz_final_consolidation', '7fbece7d5bfd', 'merge_all_heads_final')
branch_labels = None
depends_on = None

def upgrade():
    # This is a merge migration - no operations needed
    pass

def downgrade():
    # This is a merge migration - no operations needed
    pass
