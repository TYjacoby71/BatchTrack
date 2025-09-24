"""Production bootstrap 0002 - inventory, global library, and product models

Revision ID: prod_0002_inventory_products
Revises: prod_0001_core
Create Date: 2025-09-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'prod_0002_inventory_products'
down_revision = 'prod_0001_core'
branch_labels = ('production_bootstrap',)
depends_on = None


def upgrade():
    # Product category (portioning system)
    op.create_table(
        'product_category',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False, unique=True),
        sa.Column('is_typically_portioned', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('sku_name_template', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # Global library
    op.create_table(
        'global_item',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, index=True),
        sa.Column('item_type', sa.String(length=32), nullable=False, index=True),
        sa.Column('aka_names', sa.JSON(), nullable=True),
        sa.Column('density', sa.Float(), nullable=True),
        sa.Column('default_unit', sa.String(length=32), nullable=True),
        sa.Column('ingredient_category_id', sa.Integer(), nullable=True),
        sa.Column('default_is_perishable', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('recommended_shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('capacity', sa.Float(), nullable=True),
        sa.Column('capacity_unit', sa.String(length=32), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('archived_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['ingredient_category_id'], ['ingredient_category.id']),
        sa.ForeignKeyConstraint(['archived_by'], ['user.id']),
        sa.UniqueConstraint('name', 'item_type', name='_global_item_name_type_uc'),
    )
    op.create_index('ix_global_item_name', 'global_item', ['name'])
    op.create_index('ix_global_item_item_type', 'global_item', ['item_type'])

    # Inventory items
    op.create_table(
        'inventory_item',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, index=True),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('inventory_category_id', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('unit', sa.String(length=32), nullable=False),
        sa.Column('cost_per_unit', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('low_stock_threshold', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('density', sa.Float(), nullable=True),
        sa.Column('type', sa.String(length=32), nullable=False, server_default='ingredient'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('is_archived', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('is_perishable', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('expiration_date', sa.Date(), nullable=True),
        sa.Column('capacity', sa.Float(), nullable=True),
        sa.Column('capacity_unit', sa.String(length=32), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('reference_item_name', sa.String(length=128), nullable=True),
        sa.Column('density_source', sa.String(length=32), nullable=True, server_default='manual'),
        sa.Column('intermediate', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('global_item_id', sa.Integer(), nullable=True),
        sa.Column('ownership', sa.String(length=16), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['ingredient_category.id']),
        sa.ForeignKeyConstraint(['inventory_category_id'], ['inventory_category.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['global_item_id'], ['global_item.id'], ondelete='SET NULL', name='fk_inventory_item_global_item'),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.UniqueConstraint('organization_id', 'name', name='_org_name_uc'),
    )
    op.create_index('ix_inventory_item_type', 'inventory_item', ['type'])
    op.create_index('ix_inventory_item_is_archived', 'inventory_item', ['is_archived'])
    op.create_index('ix_inventory_item_global_item_id', 'inventory_item', ['global_item_id'])
    op.create_index('ix_inventory_item_organization_id', 'inventory_item', ['organization_id'])

    # Product core
    op.create_table(
        'product',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('base_unit', sa.String(length=32), nullable=False, server_default='g'),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('subcategory', sa.String(length=64), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('low_stock_threshold', sa.Float(), nullable=True, server_default='10.0'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('is_discontinued', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('shopify_product_id', sa.String(length=64), nullable=True),
        sa.Column('etsy_shop_section_id', sa.String(length=64), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.ForeignKeyConstraint(['category_id'], ['product_category.id'], name='fk_product_category'),
        sa.UniqueConstraint('name', 'organization_id', name='unique_product_name_per_org'),
    )
    op.create_index('ix_product_category_id', 'product', ['category_id'])

    op.create_table(
        'product_variant',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color', sa.String(length=32), nullable=True),
        sa.Column('material', sa.String(length=64), nullable=True),
        sa.Column('scent', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['product.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.UniqueConstraint('product_id', 'name', name='unique_product_variant'),
    )

    op.create_table(
        'product_sku',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('variant_id', sa.Integer(), nullable=True),
        sa.Column('size_label', sa.String(length=64), nullable=False, server_default='Bulk'),
        sa.Column('sku_code', sa.String(length=64), nullable=True),
        sa.Column('sku', sa.String(length=64), nullable=False, unique=True),
        sa.Column('sku_name', sa.String(length=128), nullable=True),
        sa.Column('quantity_override', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('unit', sa.String(length=32), nullable=True),
        sa.Column('low_stock_threshold', sa.Float(), nullable=True, server_default='10.0'),
        sa.Column('fifo_id', sa.String(length=32), nullable=True),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('container_id', sa.Integer(), nullable=True),
        sa.Column('retail_price', sa.Float(), nullable=True),
        sa.Column('wholesale_price', sa.Float(), nullable=True),
        sa.Column('profit_margin_target', sa.Float(), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('subcategory', sa.String(length=64), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('is_product_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('is_discontinued', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('supplier_name', sa.String(length=128), nullable=True),
        sa.Column('supplier_sku', sa.String(length=64), nullable=True),
        sa.Column('supplier_cost', sa.Float(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('weight_unit', sa.String(length=16), nullable=True),
        sa.Column('dimensions', sa.String(length=64), nullable=True),
        sa.Column('barcode', sa.String(length=128), nullable=True),
        sa.Column('upc', sa.String(length=32), nullable=True),
        sa.Column('quality_status', sa.String(length=32), nullable=True),
        sa.Column('compliance_status', sa.String(length=32), nullable=True),
        sa.Column('quality_checked_by', sa.Integer(), nullable=True),
        sa.Column('quality_checked_at', sa.DateTime(), nullable=True),
        sa.Column('location_id', sa.String(length=128), nullable=True),
        sa.Column('location_name', sa.String(length=128), nullable=True),
        sa.Column('temperature_at_time', sa.Float(), nullable=True),
        sa.Column('shopify_product_id', sa.String(length=64), nullable=True),
        sa.Column('shopify_variant_id', sa.String(length=64), nullable=True),
        sa.Column('etsy_listing_id', sa.String(length=64), nullable=True),
        sa.Column('amazon_asin', sa.String(length=64), nullable=True),
        sa.Column('marketplace_sync_status', sa.String(length=32), nullable=True),
        sa.Column('marketplace_last_sync', sa.DateTime(), nullable=True),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('is_perishable', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['product_id'], ['product.id']),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variant.id']),
        sa.ForeignKeyConstraint(['container_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['quality_checked_by'], ['user.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.UniqueConstraint('product_id', 'variant_id', 'size_label', 'fifo_id', name='unique_sku_combination'),
        sa.UniqueConstraint('barcode', name='unique_barcode'),
        sa.UniqueConstraint('upc', name='unique_upc'),
    )
    op.create_index('idx_product_variant', 'product_sku', ['product_id', 'variant_id'])
    op.create_index('idx_active_skus', 'product_sku', ['is_active', 'is_product_active'])
    op.create_index('idx_inventory_item', 'product_sku', ['inventory_item_id'])

    # Pricing and Billing snapshots
    op.create_table(
        'pricing_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('stripe_price_id', sa.String(length=128), nullable=False, unique=True),
        sa.Column('stripe_lookup_key', sa.String(length=64), nullable=False),
        sa.Column('stripe_product_id', sa.String(length=128), nullable=False),
        sa.Column('unit_amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=True, server_default='usd'),
        sa.Column('interval', sa.String(length=16), nullable=False),
        sa.Column('interval_count', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('product_name', sa.String(length=128), nullable=False),
        sa.Column('product_description', sa.Text(), nullable=True),
        sa.Column('features', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_stripe_sync', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
    )

    op.create_table(
        'billing_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('confirmed_tier', sa.String(length=32), nullable=False),
        sa.Column('confirmed_status', sa.String(length=32), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=128), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=128), nullable=True),
        sa.Column('grace_period_days', sa.Integer(), nullable=True, server_default='3'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_stripe_sync', sa.DateTime(), nullable=False),
        sa.Column('sync_source', sa.String(length=64), nullable=True, server_default='webhook'),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
    )


def downgrade():
    # Drop product first due to FK to product_category
    op.drop_table('billing_snapshots')
    op.drop_table('pricing_snapshots')
    op.drop_index('idx_inventory_item', table_name='product_sku')
    op.drop_index('idx_active_skus', table_name='product_sku')
    op.drop_index('idx_product_variant', table_name='product_sku')
    op.drop_table('product_sku')
    op.drop_table('product_variant')
    op.drop_table('product')
    op.drop_table('product_category')
    op.drop_index('ix_inventory_item_organization_id', table_name='inventory_item')
    op.drop_index('ix_inventory_item_global_item_id', table_name='inventory_item')
    op.drop_index('ix_inventory_item_is_archived', table_name='inventory_item')
    op.drop_index('ix_inventory_item_type', table_name='inventory_item')
    op.drop_table('inventory_item')
    op.drop_index('ix_global_item_item_type', table_name='global_item')
    op.drop_index('ix_global_item_name', table_name='global_item')
    op.drop_table('global_item')

