
"""Add missing fields to ProductInventory

Revision ID: add_product_fields
Revises: 2fbddb7c10ea
Create Date: 2025-06-25 20:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_product_fields'
down_revision = '2fbddb7c10ea'
branch_labels = None
depends_on = None

def upgrade():
    # Add missing columns to product_inventory
    op.add_column('product_inventory', sa.Column('variant', sa.String(128), nullable=True))
    op.add_column('product_inventory', sa.Column('size_label', sa.String(128), nullable=True))
    op.add_column('product_inventory', sa.Column('sku', sa.String(128), nullable=True))
    op.add_column('product_inventory', sa.Column('container_id', sa.Integer(), nullable=True))
    op.add_column('product_inventory', sa.Column('batch_cost_per_unit', sa.Float(), nullable=True))
    op.add_column('product_inventory', sa.Column('timestamp', sa.DateTime(), nullable=True))
    op.add_column('product_inventory', sa.Column('notes', sa.Text(), nullable=True))
    
    # Add foreign key constraint for container_id
    op.create_foreign_key('fk_product_inventory_container', 'product_inventory', 'inventory_item', ['container_id'], ['id'])

def downgrade():
    # Remove foreign key first
    op.drop_constraint('fk_product_inventory_container', 'product_inventory', type_='foreignkey')
    
    # Remove columns
    op.drop_column('product_inventory', 'notes')
    op.drop_column('product_inventory', 'timestamp')
    op.drop_column('product_inventory', 'batch_cost_per_unit')
    op.drop_column('product_inventory', 'container_id')
    op.drop_column('product_inventory', 'sku')
    op.drop_column('product_inventory', 'size_label')
    op.drop_column('product_inventory', 'variant')
