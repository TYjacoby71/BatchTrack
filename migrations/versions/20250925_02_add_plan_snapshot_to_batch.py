"""
Add plan_snapshot JSON to batch

Revision ID: 20250925_02
Revises: 20250925_01_add_portion_columns_to_recipe_and_batch
Create Date: 2025-09-25
"""

from alembic import op
import sqlalchemy as sa


revision = '20250925_02'
down_revision = '20250925_01_add_portion_columns_to_recipe_and_batch'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('batch') as batch_op:
        batch_op.add_column(sa.Column('plan_snapshot', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('batch') as batch_op:
        batch_op.drop_column('plan_snapshot')

