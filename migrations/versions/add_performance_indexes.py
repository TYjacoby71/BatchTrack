
"""Add database indexes for performance

Revision ID: dbindex
Revises: initial
Create Date: 2025-05-19 18:45:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'dbindex'
down_revision = 'update_inventory_types'
branch_labels = None
depends_on = None

def upgrade():
    # Batch table indexes
    op.create_index('idx_batch_status', 'batch', ['status'])
    op.create_index('idx_batch_label_code', 'batch', ['label_code'])
    op.create_index('idx_batch_started_at', 'batch', ['started_at'])

    # Inventory tracking indexes  
    op.create_index('idx_inventory_history_timestamp', 'inventory_history', ['timestamp'])
    op.create_index('idx_inventory_history_change_type', 'inventory_history', ['change_type'])

    # Product and recipe indexes
    op.create_index('idx_product_variation_sku', 'product_variation', ['sku'])
    op.create_index('idx_recipe_name', 'recipe', ['name'])

    # Inventory item indexes
    op.create_index('idx_inventory_item_type', 'inventory_item', ['type'])
    op.create_index('idx_inventory_item_name', 'inventory_item', ['name'])

def downgrade():
    op.drop_index('idx_batch_status')
    op.drop_index('idx_batch_label_code')
    op.drop_index('idx_batch_started_at')
    op.drop_index('idx_inventory_history_timestamp')
    op.drop_index('idx_inventory_history_change_type')
    op.drop_index('idx_product_variation_sku')
    op.drop_index('idx_recipe_name')
    op.drop_index('idx_inventory_item_type')
    op.drop_index('idx_inventory_item_name')
