
"""fix_user_role_assignment_constraint_final

Revision ID: fix_user_role_assignment_constraint_final
Revises: fix_user_role_assignment_constraint
Create Date: 2025-07-22 04:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_user_role_assignment_constraint_final'
down_revision = 'fix_user_role_assignment_constraint'
branch_labels = None
depends_on = None

def upgrade():
    # Drop the problematic constraint if it exists
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('check_exactly_one_role', type_='check')
        except:
            # Constraint might not exist, continue
            pass

def downgrade():
    # Add the constraint back
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'check_exactly_one_role',
            '(role_id IS NOT NULL AND developer_role_id IS NULL) OR (role_id IS NULL AND developer_role_id IS NOT NULL)'
        )
