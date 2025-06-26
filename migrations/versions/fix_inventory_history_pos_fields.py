
"""Fix missing POS integration fields in inventory_history

Revision ID: fix_inventory_history_pos_fields
Revises: update_product_sku_history_fifo_source
Create Date: 2025-06-26 19:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_inventory_history_pos_fields'
down_revision = 'e04a3508f9f7_initial_schema_with_all_models'
branch_labels = None
depends_on = None

def upgrade():
    # Add POS integration fields to inventory_history table
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('reservation_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('is_reserved', sa.Boolean(), nullable=True, default=False))

def downgrade():
    # Remove POS integration fields from inventory_history
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.drop_column('is_reserved')
        batch_op.drop_column('reservation_id')
        batch_op.drop_column('order_id')
