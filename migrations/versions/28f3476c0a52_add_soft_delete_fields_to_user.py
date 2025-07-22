
"""add_soft_delete_fields_to_user

Revision ID: 28f3476c0a52
Revises: bfc8381314d8
Create Date: 2025-07-22 01:50:00.442754

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '28f3476c0a52'
down_revision = 'bfc8381314d8'
branch_labels = None
depends_on = None


def upgrade():
    # Add soft delete fields to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deleted_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=True, default=False))
        
        # Add foreign key constraint for deleted_by
        batch_op.create_foreign_key('fk_user_deleted_by', 'user', ['deleted_by'], ['id'])


def downgrade():
    # Remove soft delete fields from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_deleted_by', type_='foreignkey')
        batch_op.drop_column('is_deleted')
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')
