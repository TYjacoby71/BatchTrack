"""fix_developer_users

Revision ID: fix_developer_users
Revises: create_user_role_assignment
Create Date: 2025-07-17 20:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_developer_users'
down_revision = 'create_user_role_assignment'
branch_labels = None
depends_on = None


def upgrade():
    # Make organization_id nullable for developer users
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('organization_id',
                            existing_type=sa.Integer(),
                            nullable=True)


def downgrade():
    # Revert organization_id to not nullable
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('organization_id',
                            existing_type=sa.Integer(),
                            nullable=False)