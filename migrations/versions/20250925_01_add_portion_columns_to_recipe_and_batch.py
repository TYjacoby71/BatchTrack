"""
Add portion columns to recipe and batch: is_portioned, portion_name, counts

Revision ID: 20250925_01
Revises: 20250924_01
Create Date: 2025-09-25
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250925_01'
down_revision = '20250924_01'
branch_labels = None
depends_on = None


def upgrade():
    # Recipe columns
    with op.batch_alter_table('recipe') as batch_op:
        batch_op.add_column(sa.Column('is_portioned', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('portion_name', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('portion_count', sa.Integer(), nullable=True))

    # Batch columns
    with op.batch_alter_table('batch') as batch_op:
        batch_op.add_column(sa.Column('is_portioned', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('portion_name', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('projected_portions', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('final_portions', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('batch') as batch_op:
        batch_op.drop_column('final_portions')
        batch_op.drop_column('projected_portions')
        batch_op.drop_column('portion_name')
        batch_op.drop_column('is_portioned')

    with op.batch_alter_table('recipe') as batch_op:
        batch_op.drop_column('portion_count')
        batch_op.drop_column('portion_name')
        batch_op.drop_column('is_portioned')

