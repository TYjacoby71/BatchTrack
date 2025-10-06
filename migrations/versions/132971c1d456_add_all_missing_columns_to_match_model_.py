"""add all missing columns to match model definitions

Revision ID: 132971c1d456
Revises: 4481595c5f02
Create Date: 2025-07-31 19:03:22.963930

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '132971c1d456'
down_revision = '4481595c5f02'
branch_labels = None
depends_on = None


def upgrade():
    """
    TEMPORARY MIGRATION: Add all missing columns WITHOUT any constraints
    This allows seeding to work without constraint violations
    TODO: Add constraints back in a separate migration after seeding
    """
    
    # Helper function to check if column exists
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    
    def column_exists(table_name, column_name):
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns

    # Add all missing columns to product_sku table WITHOUT constraints
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        # Add missing columns from ProductSKU model (only if they don't exist)
        columns_to_add = [
            ('variant_id', sa.Integer()),
            ('size_label', sa.String(length=64)),
            ('sku_name', sa.String(length=128)),
            ('unit', sa.String(length=32)),
            ('low_stock_threshold', sa.Float()),
            ('fifo_id', sa.String(length=32)),
            ('batch_id', sa.Integer()),
            ('container_id', sa.Integer()),
            ('retail_price', sa.Float()),
            ('wholesale_price', sa.Float()),
            ('profit_margin_target', sa.Float()),
            ('category', sa.String(length=64)),
            ('subcategory', sa.String(length=64)),
            ('tags', sa.Text()),
            ('is_product_active', sa.Boolean()),
            ('is_discontinued', sa.Boolean()),
            ('created_by', sa.Integer()),
            ('supplier_name', sa.String(length=128)),
            ('supplier_sku', sa.String(length=64)),
            ('supplier_cost', sa.Float()),
            ('weight', sa.Float()),
            ('weight_unit', sa.String(length=16)),
            ('dimensions', sa.String(length=64)),
            ('barcode', sa.String(length=128)),
            ('barcode_type', sa.String(length=20)),
            ('upc', sa.String(length=32)),
            ('quality_status', sa.String(length=32)),
            ('compliance_status', sa.String(length=32)),
            ('quality_checked_by', sa.Integer()),
            ('quality_checked_at', sa.DateTime()),
            ('location_id', sa.String(length=128)),
            ('location_name', sa.String(length=128)),
            ('temperature_at_time', sa.Float()),
            ('shopify_product_id', sa.String(length=64)),
            ('shopify_variant_id', sa.String(length=64)),
            ('etsy_listing_id', sa.String(length=64)),
            ('amazon_asin', sa.String(length=64)),
            ('marketplace_sync_status', sa.String(length=32)),
            ('marketplace_last_sync', sa.DateTime()),
            ('expiration_date', sa.DateTime()),
            ('is_perishable', sa.Boolean()),
            ('shelf_life_days', sa.Integer())
        ]
        
        for col_name, col_type in columns_to_add:
            if not column_exists('product_sku', col_name):
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))

    # Add missing ProductSKUHistory table columns (only if they don't exist)
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        history_columns_to_add = [
            ('inventory_item_id', sa.Integer()),
            ('remaining_quantity', sa.Float()),
            ('unit_cost', sa.Float()),
            ('sale_price', sa.Float()),
            ('customer', sa.String(length=128)),
            ('fifo_code', sa.String(length=64)),
            ('fifo_reference_id', sa.Integer()),
            ('fifo_source', sa.String(length=128)),
            ('is_perishable', sa.Boolean()),
            ('shelf_life_days', sa.Integer()),
            ('expiration_date', sa.DateTime()),
            ('container_id', sa.Integer()),
            ('notes', sa.Text()),
            ('note', sa.Text()),
            ('created_by', sa.Integer()),
            ('order_id', sa.String(length=64)),
            ('reservation_id', sa.String(length=64)),
            ('is_reserved', sa.Boolean()),
            ('sale_location', sa.String(length=64)),
            ('quantity_used', sa.Float()),
            ('batch_number', sa.String(length=128)),
            ('lot_number', sa.String(length=128)),
            ('temperature_at_time', sa.Float()),
            ('location_id', sa.String(length=128)),
            ('location_name', sa.String(length=128)),
            ('quality_status', sa.String(length=32)),
            ('compliance_status', sa.String(length=32)),
            ('quality_checked_by', sa.Integer()),
            ('marketplace_order_id', sa.String(length=128)),
            ('marketplace_source', sa.String(length=32))
        ]
        
        for col_name, col_type in history_columns_to_add:
            if not column_exists('product_sku_history', col_name):
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))

    print("✅ Migration completed: All columns added WITHOUT constraints")
    print("⚠️  TODO: Create a separate migration to add constraints after seeding")


def downgrade():
    """Remove all added columns"""

    # Drop ProductSKUHistory additions
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        # Drop columns
        batch_op.drop_column('marketplace_source')
        batch_op.drop_column('marketplace_order_id')
        batch_op.drop_column('quality_checked_by')
        batch_op.drop_column('compliance_status')
        batch_op.drop_column('quality_status')
        batch_op.drop_column('location_name')
        batch_op.drop_column('location_id')
        batch_op.drop_column('temperature_at_time')
        batch_op.drop_column('lot_number')
        batch_op.drop_column('batch_number')
        batch_op.drop_column('quantity_used')
        batch_op.drop_column('sale_location')
        batch_op.drop_column('is_reserved')
        batch_op.drop_column('reservation_id')
        batch_op.drop_column('order_id')
        batch_op.drop_column('created_by')
        batch_op.drop_column('note')
        batch_op.drop_column('notes')
        batch_op.drop_column('container_id')
        batch_op.drop_column('expiration_date')
        batch_op.drop_column('shelf_life_days')
        batch_op.drop_column('is_perishable')
        batch_op.drop_column('fifo_source')
        batch_op.drop_column('fifo_reference_id')
        batch_op.drop_column('fifo_code')
        batch_op.drop_column('customer')
        batch_op.drop_column('sale_price')
        batch_op.drop_column('unit_cost')
        batch_op.drop_column('remaining_quantity')
        batch_op.drop_column('inventory_item_id')

    # Drop ProductSKU additions
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        # Drop all added columns
        batch_op.drop_column('shelf_life_days')
        batch_op.drop_column('is_perishable')
        batch_op.drop_column('expiration_date')
        batch_op.drop_column('marketplace_last_sync')
        batch_op.drop_column('marketplace_sync_status')
        batch_op.drop_column('amazon_asin')
        batch_op.drop_column('etsy_listing_id')
        batch_op.drop_column('shopify_variant_id')
        batch_op.drop_column('shopify_product_id')
        batch_op.drop_column('temperature_at_time')
        batch_op.drop_column('location_name')
        batch_op.drop_column('location_id')
        batch_op.drop_column('quality_checked_at')
        batch_op.drop_column('quality_checked_by')
        batch_op.drop_column('compliance_status')
        batch_op.drop_column('quality_status')
        batch_op.drop_column('upc')
        batch_op.drop_column('barcode_type')
        batch_op.drop_column('barcode')
        batch_op.drop_column('dimensions')
        batch_op.drop_column('weight_unit')
        batch_op.drop_column('weight')
        batch_op.drop_column('supplier_cost')
        batch_op.drop_column('supplier_sku')
        batch_op.drop_column('supplier_name')
        batch_op.drop_column('created_by')
        batch_op.drop_column('is_discontinued')
        batch_op.drop_column('is_product_active')
        batch_op.drop_column('tags')
        batch_op.drop_column('subcategory')
        batch_op.drop_column('category')
        batch_op.drop_column('profit_margin_target')
        batch_op.drop_column('wholesale_price')
        batch_op.drop_column('retail_price')
        batch_op.drop_column('container_id')
        batch_op.drop_column('batch_id')
        batch_op.drop_column('fifo_id')
        batch_op.drop_column('low_stock_threshold')
        batch_op.drop_column('unit')
        batch_op.drop_column('sku_name')
        batch_op.drop_column('size_label')
        batch_op.drop_column('variant_id')