

"""Expand ProductSKU with all batch-related fields

Revision ID: expand_product_sku_fields
Revises: drop_old_product_tables
Create Date: 2025-06-25 23:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers
revision = 'expand_product_sku_fields'
down_revision = 'drop_old_product_tables'
branch_labels = None
depends_on = None

def upgrade():
    # Add new fields to ProductSKU table
    op.add_column('product_sku', sa.Column('product_id', sa.Integer(), nullable=True))
    op.add_column('product_sku', sa.Column('variant_id', sa.Integer(), nullable=True))
    op.add_column('product_sku', sa.Column('sku_name', sa.String(128), nullable=True))
    op.add_column('product_sku', sa.Column('remaining_quantity', sa.Float(), default=0.0))
    op.add_column('product_sku', sa.Column('original_quantity', sa.Float(), default=0.0))
    op.add_column('product_sku', sa.Column('retail_price', sa.Float(), nullable=True))
    op.add_column('product_sku', sa.Column('fifo_id', sa.String(64), nullable=True))
    op.add_column('product_sku', sa.Column('change_type', sa.String(32), default='batch_addition'))
    op.add_column('product_sku', sa.Column('container_size', sa.String(128), nullable=True))
    op.add_column('product_sku', sa.Column('container_line_cost', sa.Float(), nullable=True))
    op.add_column('product_sku', sa.Column('batch_completed_at', sa.DateTime(), nullable=True))
    op.add_column('product_sku', sa.Column('customer', sa.String(128), nullable=True))
    
    # Update the unique constraint to include fifo_id
    op.drop_constraint('unique_sku_combination', 'product_sku', type_='unique')
    op.create_unique_constraint('unique_sku_fifo_combination', 'product_sku', 
                               ['product_name', 'variant_name', 'size_label', 'fifo_id'])
    
    # Add new indexes
    op.create_index('idx_batch_fifo', 'product_sku', ['batch_id', 'fifo_id'])
    op.create_index('idx_low_stock', 'product_sku', ['current_quantity', 'low_stock_threshold'])
    
    # Add new fields to ProductSKUHistory table
    op.add_column('product_sku_history', sa.Column('fifo_code', sa.String(64), nullable=True))
    
    # Add new indexes to history table
    op.create_index('idx_change_type', 'product_sku_history', ['change_type'])
    op.create_index('idx_fifo_code', 'product_sku_history', ['fifo_code'])

def downgrade():
    # Remove added columns and constraints
    op.drop_index('idx_fifo_code', 'product_sku_history')
    op.drop_index('idx_change_type', 'product_sku_history')
    op.drop_column('product_sku_history', 'fifo_code')
    
    op.drop_index('idx_low_stock', 'product_sku')
    op.drop_index('idx_batch_fifo', 'product_sku')
    op.drop_constraint('unique_sku_fifo_combination', 'product_sku', type_='unique')
    op.create_unique_constraint('unique_sku_combination', 'product_sku', 
                               ['product_name', 'variant_name', 'size_label'])
    
    op.drop_column('product_sku', 'customer')
    op.drop_column('product_sku', 'batch_completed_at')
    op.drop_column('product_sku', 'container_line_cost')
    op.drop_column('product_sku', 'container_size')
    op.drop_column('product_sku', 'change_type')
    op.drop_column('product_sku', 'fifo_id')
    op.drop_column('product_sku', 'retail_price')
    op.drop_column('product_sku', 'original_quantity')
    op.drop_column('product_sku', 'remaining_quantity')
    op.drop_column('product_sku', 'sku_name')
    op.drop_column('product_sku', 'variant_id')
    op.drop_column('product_sku', 'product_id')

