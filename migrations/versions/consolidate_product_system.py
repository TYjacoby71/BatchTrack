
"""Consolidate product system - remove redundant fields

Revision ID: consolidate_product_system
Revises: add_product_sku_table
Create Date: 2025-06-25 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'consolidate_product_system'
down_revision = 'add_product_sku_table'
branch_labels = None
depends_on = None

def upgrade():
    # Remove redundant columns from product_inventory (keep only sku_id reference)
    with op.batch_alter_table('product_inventory') as batch_op:
        batch_op.drop_column('product_id')
        batch_op.drop_column('variant_id') 
        batch_op.drop_column('variant')
        batch_op.drop_column('size_label')
        batch_op.drop_column('sku')
        batch_op.drop_column('unit')
    
    # Remove redundant columns from product_inventory_history
    with op.batch_alter_table('product_inventory_history') as batch_op:
        batch_op.drop_column('unit')
    
    # Remove redundant inventory fields from product table
    with op.batch_alter_table('product') as batch_op:
        batch_op.drop_column('low_stock_threshold')

def downgrade():
    # Add back removed columns for rollback
    with op.batch_alter_table('product_inventory') as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('variant_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('variant', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('size_label', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('sku', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('unit', sa.String(32), nullable=True))
    
    with op.batch_alter_table('product_inventory_history') as batch_op:
        batch_op.add_column(sa.Column('unit', sa.String(32), nullable=True))
    
    with op.batch_alter_table('product') as batch_op:
        batch_op.add_column(sa.Column('low_stock_threshold', sa.Float(), default=0))
