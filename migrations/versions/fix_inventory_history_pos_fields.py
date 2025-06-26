
"""Fix missing POS integration fields in inventory_history

Revision ID: fix_inventory_history_pos_fields
Revises: update_product_sku_history_fifo_source
Create Date: 2025-06-26 19:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_inventory_history_pos_fields'
down_revision = 'update_product_sku_history_fifo_source'
branch_labels = None
depends_on = None

def upgrade():
    # Check if columns already exist in inventory_history table
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('inventory_history')]
    
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        if 'order_id' not in existing_columns:
            batch_op.add_column(sa.Column('order_id', sa.String(length=64), nullable=True))
        
        if 'reservation_id' not in existing_columns:
            batch_op.add_column(sa.Column('reservation_id', sa.String(length=64), nullable=True))
        
        if 'is_reserved' not in existing_columns:
            batch_op.add_column(sa.Column('is_reserved', sa.Boolean(), nullable=True, default=False))

def downgrade():
    # Remove POS integration fields from inventory_history
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('inventory_history')]
    
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        if 'is_reserved' in existing_columns:
            batch_op.drop_column('is_reserved')
        
        if 'reservation_id' in existing_columns:
            batch_op.drop_column('reservation_id')
        
        if 'order_id' in existing_columns:
            batch_op.drop_column('order_id')
