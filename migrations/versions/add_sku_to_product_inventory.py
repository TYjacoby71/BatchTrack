
"""Add SKU column to ProductInventory

Revision ID: add_sku_to_product_inventory
Revises: 8dfa489d825b
Create Date: 2025-06-06 01:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_sku_to_product_inventory'
down_revision = '8dfa489d825b'
branch_labels = None
depends_on = None

def upgrade():
    # Add SKU column to product_inventory table
    op.add_column('product_inventory', sa.Column('sku', sa.String(100), nullable=True))

def downgrade():
    # Remove SKU column from product_inventory table
    op.drop_column('product_inventory', 'sku')
