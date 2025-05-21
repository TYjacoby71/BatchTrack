"""empty message

Revision ID: 5adabbbfd04c
Revises: d385ba5621fc
Create Date: 2025-05-21 15:37

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5adabbbfd04c'
down_revision = 'd385ba5621fc'
branch_labels = None
depends_on = None


def upgrade():
    # Update inventory_history table
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fifo_reference_id', sa.Integer(), nullable=True))
        batch_op.drop_column('source_fifo_id')
        batch_op.drop_column('credited_to_fifo_id')
        batch_op.drop_column('source')
        batch_op.create_foreign_key('fk_inventory_history_fifo_reference_id_inventory_history', 'inventory_history', ['fifo_reference_id'], ['id'])

    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shelf_life_days', sa.Integer(), nullable=True))


def downgrade():
    # Update inventory_history table
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.drop_constraint('fk_inventory_history_fifo_reference_id_inventory_history', type_='foreignkey')
        batch_op.add_column(sa.Column('source', sa.VARCHAR(length=32), nullable=True))
        batch_op.add_column(sa.Column('credited_to_fifo_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('source_fifo_id', sa.INTEGER(), nullable=True))
        batch_op.drop_column('fifo_reference_id')

    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.drop_column('shelf_life_days')