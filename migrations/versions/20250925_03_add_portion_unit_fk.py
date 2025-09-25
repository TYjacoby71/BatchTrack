"""
Add portion_unit_id FK to recipe and batch

Revision ID: 20250925_03
Revises: 20250925_02
Create Date: 2025-09-25
"""

from alembic import op
import sqlalchemy as sa


revision = '20250925_03'
down_revision = '20250925_02'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('recipe') as batch_op:
        batch_op.add_column(sa.Column('portion_unit_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_recipe_portion_unit', 'unit', ['portion_unit_id'], ['id'])

    with op.batch_alter_table('batch') as batch_op:
        batch_op.add_column(sa.Column('portion_unit_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_batch_portion_unit', 'unit', ['portion_unit_id'], ['id'])


def downgrade():
    with op.batch_alter_table('batch') as batch_op:
        batch_op.drop_constraint('fk_batch_portion_unit', type_='foreignkey')
        batch_op.drop_column('portion_unit_id')

    with op.batch_alter_table('recipe') as batch_op:
        batch_op.drop_constraint('fk_recipe_portion_unit', type_='foreignkey')
        batch_op.drop_column('portion_unit_id')

