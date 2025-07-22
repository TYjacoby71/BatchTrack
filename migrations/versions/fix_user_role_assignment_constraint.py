
"""fix_user_role_assignment_constraint

Revision ID: fix_user_role_assignment_constraint
Revises: consolidate_all_heads_final
Create Date: 2025-07-22 04:37:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_user_role_assignment_constraint'
down_revision = 'consolidate_all_heads_final'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing constraint if it exists and recreate the table with proper constraints
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        # Add check constraint to ensure exactly one role type is set
        batch_op.create_check_constraint(
            'check_exactly_one_role',
            '(role_id IS NOT NULL AND developer_role_id IS NULL) OR (role_id IS NULL AND developer_role_id IS NOT NULL)'
        )


def downgrade():
    # Remove the constraint
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.drop_constraint('check_exactly_one_role', type_='check')
