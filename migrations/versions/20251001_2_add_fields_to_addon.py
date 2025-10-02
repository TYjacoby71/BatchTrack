"""add function_key and retention_extension_days to addon

Revision ID: 20251001_2
Revises: 20251001_1
Create Date: 2025-10-01
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251001_2'
down_revision = '20251001_1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('addon', schema=None) as batch_op:
        batch_op.add_column(sa.Column('function_key', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('retention_extension_days', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('addon', schema=None) as batch_op:
        batch_op.drop_column('retention_extension_days')
        batch_op.drop_column('function_key')

