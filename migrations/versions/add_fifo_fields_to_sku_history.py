

"""Add FIFO fields to ProductSKUHistory

Revision ID: add_fifo_fields_to_sku_history
Revises: drop_old_product_tables
Create Date: 2025-06-25 23:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_fifo_fields_to_sku_history'
down_revision = 'drop_old_product_tables'
branch_labels = None
depends_on = None

def upgrade():
    # Add FIFO fields to product_sku_history
    op.add_column('product_sku_history', sa.Column('remaining_quantity', sa.Float(), default=0.0))
    op.add_column('product_sku_history', sa.Column('original_quantity', sa.Float(), nullable=True))
    op.add_column('product_sku_history', sa.Column('unit', sa.String(32), nullable=True))
    op.add_column('product_sku_history', sa.Column('fifo_code', sa.String(64), nullable=True))
    op.add_column('product_sku_history', sa.Column('container_id', sa.Integer(), nullable=True))
    op.add_column('product_sku_history', sa.Column('is_perishable', sa.Boolean(), default=False))
    op.add_column('product_sku_history', sa.Column('shelf_life_days', sa.Integer(), nullable=True))
    op.add_column('product_sku_history', sa.Column('expiration_date', sa.DateTime(), nullable=True))
    
    # Add foreign key constraint for container_id
    op.create_foreign_key('fk_sku_history_container', 'product_sku_history', 'inventory_item', ['container_id'], ['id'])
    
    # Create indexes for FIFO performance
    op.create_index('idx_sku_remaining', 'product_sku_history', ['sku_id', 'remaining_quantity'])
    op.create_index('idx_sku_timestamp', 'product_sku_history', ['sku_id', 'timestamp'])
    
    # Update existing records to have unit from their SKU
    op.execute("""
        UPDATE product_sku_history 
        SET unit = (
            SELECT product_sku.unit 
            FROM product_sku 
            WHERE product_sku.id = product_sku_history.sku_id
        )
        WHERE unit IS NULL
    """)
    
    # Make unit column non-nullable now that it's populated
    op.alter_column('product_sku_history', 'unit', nullable=False)

def downgrade():
    op.drop_index('idx_sku_timestamp', 'product_sku_history')
    op.drop_index('idx_sku_remaining', 'product_sku_history')
    op.drop_constraint('fk_sku_history_container', 'product_sku_history', type_='foreignkey')
    op.drop_column('product_sku_history', 'expiration_date')
    op.drop_column('product_sku_history', 'shelf_life_days')
    op.drop_column('product_sku_history', 'is_perishable')
    op.drop_column('product_sku_history', 'container_id')
    op.drop_column('product_sku_history', 'fifo_code')
    op.drop_column('product_sku_history', 'unit')
    op.drop_column('product_sku_history', 'original_quantity')
    op.drop_column('product_sku_history', 'remaining_quantity')

