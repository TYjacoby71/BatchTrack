
"""fix_product_sku_history_schema

Revision ID: fix_product_sku_history_schema
Revises: clean_product_sku_history_fix
Create Date: 2025-07-07 20:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_product_sku_history_schema'
down_revision = 'clean_product_sku_history_fix'
branch_labels = None
depends_on = None

def upgrade():
    # Check if sku_id column exists and remove it
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        # Try to drop the sku_id column if it exists
        try:
            batch_op.drop_column('sku_id')
        except:
            pass  # Column might not exist
    
    # Ensure inventory_item_id foreign key is correct
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        # Drop existing foreign key if it exists
        try:
            batch_op.drop_constraint('fk_product_sku_history_inventory_item_id', type_='foreignkey')
        except:
            pass
        
        # Add correct foreign key
        batch_op.create_foreign_key(
            'fk_product_sku_history_inventory_item_id',
            'inventory_item',
            ['inventory_item_id'],
            ['id']
        )

def downgrade():
    # Reverse the changes
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        batch_op.drop_constraint('fk_product_sku_history_inventory_item_id', type_='foreignkey')
        batch_op.add_column(sa.Column('sku_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            'fk_product_sku_history_sku_id',
            'product_sku',
            ['sku_id'],
            ['inventory_item_id']
        )
