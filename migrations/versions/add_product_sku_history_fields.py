"""Add missing fields to ProductSKUHistory

Revision ID: add_product_sku_history_fields
Revises: add_pos_integration_fields
Create Date: 2025-01-26 18:52:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_product_sku_history_fields'
down_revision = 'add_pos_integration_fields'
branch_labels = None
depends_on = None

def upgrade():
    # Add missing fields to product_sku_history table
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fifo_reference_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('quantity_used', sa.Float(), nullable=True, default=0.0))
        batch_op.add_column(sa.Column('used_for_batch_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('order_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('reservation_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('is_reserved', sa.Boolean(), nullable=True, default=False))
        batch_op.add_column(sa.Column('sale_location', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('note', sa.Text(), nullable=True))

        # Add foreign key constraints
        batch_op.create_foreign_key('fk_product_sku_history_fifo_reference', 'product_sku_history', ['fifo_reference_id'], ['id'])
        batch_op.create_foreign_key('fk_product_sku_history_used_for_batch', 'batch', ['used_for_batch_id'], ['id'])

        # Add indexes
        batch_op.create_index('idx_fifo_reference', ['fifo_reference_id'], unique=False)
        batch_op.create_index('idx_order_reservation', ['order_id', 'reservation_id'], unique=False)
        batch_op.create_index('idx_sale_location', ['sale_location'], unique=False)

def downgrade():
    # Remove added fields and constraints
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        batch_op.drop_index('idx_sale_location')
        batch_op.drop_index('idx_order_reservation')
        batch_op.drop_index('idx_fifo_reference')

        batch_op.drop_constraint('fk_product_sku_history_used_for_batch', type_='foreignkey')
        batch_op.drop_constraint('fk_product_sku_history_fifo_reference', type_='foreignkey')

        batch_op.drop_column('note')
        batch_op.drop_column('sale_location')
        batch_op.drop_column('is_reserved')
        batch_op.drop_column('reservation_id')
        batch_op.drop_column('order_id')
        batch_op.drop_column('used_for_batch_id')
        batch_op.drop_column('quantity_used')
        batch_op.drop_column('fifo_reference_id')