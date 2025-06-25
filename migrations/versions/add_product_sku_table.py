
"""Add ProductSKU table and update relationships

Revision ID: add_product_sku_table
Revises: dc2034e4443f
Create Date: 2025-06-25 22:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_product_sku_table'
down_revision = 'dc2034e4443f'
branch_labels = None
depends_on = None

def upgrade():
    # Create ProductSKU table
    op.create_table('product_sku',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('product.id'), nullable=False),
        sa.Column('variant_id', sa.Integer(), sa.ForeignKey('product_variation.id'), nullable=False),
        sa.Column('variant_name', sa.String(128), nullable=False),
        sa.Column('size_label', sa.String(128), nullable=False),
        sa.Column('sku_code', sa.String(128), nullable=True),
        sa.Column('unit', sa.String(32), nullable=False),
        sa.Column('low_stock_threshold', sa.Float(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.UniqueConstraint('product_id', 'variant_id', 'size_label', name='unique_sku_combination'),
        sa.UniqueConstraint('sku_code', name='unique_sku_code')
    )
    
    # Add sku_id column to product_inventory using batch mode for SQLite
    with op.batch_alter_table('product_inventory', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sku_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_product_inventory_sku_id', 'product_sku', ['sku_id'], ['id'])
    
    # Add sku_id column to product_inventory_history using batch mode for SQLite
    with op.batch_alter_table('product_inventory_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sku_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_product_inventory_history_sku_id', 'product_sku', ['sku_id'], ['id'])

def downgrade():
    # Remove sku_id columns using batch mode for SQLite
    with op.batch_alter_table('product_inventory_history', schema=None) as batch_op:
        batch_op.drop_constraint('fk_product_inventory_history_sku_id', type_='foreignkey')
        batch_op.drop_column('sku_id')
    
    with op.batch_alter_table('product_inventory', schema=None) as batch_op:
        batch_op.drop_constraint('fk_product_inventory_sku_id', type_='foreignkey')
        batch_op.drop_column('sku_id')
    
    # Drop ProductSKU table
    op.drop_table('product_sku')
