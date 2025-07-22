
"""merge_all_current_heads

Revision ID: merge_all_current_heads
Revises: fd6ec9059553, create_developer_tables, add_developer_role_id, fix_user_role_assignment_constraint, fix_user_role_assignment_constraint_final
Create Date: 2025-07-22 04:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_all_current_heads'
down_revision = ('fd6ec9059553', 'create_developer_tables', 'add_developer_role_id', 'fix_user_role_assignment_constraint', 'fix_user_role_assignment_constraint_final')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration to consolidate all current heads
    # No actual schema changes needed
    pass


def downgrade():
    # This is a merge migration to consolidate all current heads
    # No actual schema changes needed
    pass
