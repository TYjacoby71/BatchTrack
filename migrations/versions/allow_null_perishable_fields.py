
"""Allow null perishable fields

Revision ID: allow_null_perishable
Revises: 2af2ecb1908a
Create Date: 2025-05-14 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'allow_null_perishable'
down_revision = '2af2ecb1908a'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('batch', schema=None) as batch_op:
        batch_op.alter_column('is_perishable',
                existing_type=sa.Boolean(),
                nullable=True,
                server_default=None)
        batch_op.alter_column('shelf_life_days',
                existing_type=sa.Integer(),
                nullable=True)
        batch_op.alter_column('expiration_date',
                existing_type=sa.DateTime(),
                nullable=True)

def downgrade():
    with op.batch_alter_table('batch', schema=None) as batch_op:
        batch_op.alter_column('is_perishable',
                existing_type=sa.Boolean(),
                nullable=False,
                server_default=sa.text('false'))
        batch_op.alter_column('shelf_life_days',
                existing_type=sa.Integer(),
                nullable=False)
        batch_op.alter_column('expiration_date',
                existing_type=sa.DateTime(),
                nullable=False)
