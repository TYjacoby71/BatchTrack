
"""merge_all_heads_final

Revision ID: merge_all_heads_final  
Revises: add_is_organization_owner_flag, fix_user_role_assignment_null_constraint
Create Date: 2025-07-22 22:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_all_heads_final'
down_revision = ('add_is_organization_owner_flag', 'fix_user_role_assignment_null_constraint')
branch_labels = None
depends_on = None

def upgrade():
    # This is a merge migration to consolidate all current heads
    # No actual schema changes needed - just merging the history
    pass

def downgrade():
    # This is a merge migration to consolidate all current heads  
    # No actual schema changes needed - just merging the history
    pass
