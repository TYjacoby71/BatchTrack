
"""Drop old product tables

Revision ID: drop_old_product_tables
Revises: consolidate_to_single_sku_table
Create Date: 2025-06-25 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'drop_old_product_tables'
down_revision = 'consolidate_to_single_sku_table'
branch_labels = None
depends_on = None

def upgrade():
    # Drop foreign key constraints first
    with op.batch_alter_table('product_sku') as batch_op:
        batch_op.drop_constraint('fk_product_sku_product_id_product', type_='foreignkey')
        batch_op.drop_constraint('fk_product_sku_variant_id_product_variation', type_='foreignkey')
        batch_op.drop_column('product_id')
        batch_op.drop_column('variant_id')
    
    # Drop old tables in correct order (children first)
    op.drop_table('product_inventory_history')
    op.drop_table('product_inventory')
    op.drop_table('product_event')
    op.drop_table('product_variation')
    op.drop_table('product')

def downgrade():
    # Note: This is a destructive migration - downgrade not fully supported
    # Would need to recreate all old tables and data
    pass
