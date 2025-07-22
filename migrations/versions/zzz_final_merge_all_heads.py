
"""merge_all_heads_consolidated

Revision ID: zzz_final_merge_all_heads
Revises: merge_all_current_heads, fix_user_role_assignment_null_constraint
Create Date: 2025-07-22 22:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'zzz_final_merge_all_heads'
down_revision = ('merge_all_current_heads', 'fix_user_role_assignment_null_constraint')
branch_labels = None
depends_on = None

def upgrade():
    # This is a merge migration to consolidate all remaining heads
    # No actual schema changes needed
    pass

def downgrade():
    # This is a merge migration to consolidate all remaining heads  
    # No actual schema changes needed
    pass
