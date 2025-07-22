
"""add_developer_role_id_to_user_role_assignment

Revision ID: add_developer_role_id
Revises: consolidate_all_heads_final
Create Date: 2025-01-22 04:09:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_developer_role_id'
down_revision = 'consolidate_all_heads_final'
branch_labels = None
depends_on = None


def upgrade():
    # Add developer_role_id column to user_role_assignment table
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('developer_role_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_user_role_assignment_developer_role', 'developer_role', ['developer_role_id'], ['id'])


def downgrade():
    # Remove developer_role_id column from user_role_assignment table
    with op.batch_alter_table('user_role_assignment', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_role_assignment_developer_role', type_='foreignkey')
        batch_op.drop_column('developer_role_id')
