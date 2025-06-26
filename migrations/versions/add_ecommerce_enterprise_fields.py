
"""Add comprehensive e-commerce and enterprise fields

Revision ID: add_ecommerce_enterprise_fields
Revises: expand_product_sku_fields
Create Date: 2025-06-25 23:58:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_ecommerce_enterprise_fields'
down_revision = 'expand_product_sku_fields'
branch_labels = None
depends_on = None

def upgrade():
    # Add e-commerce and marketing fields to ProductSKU
    with op.batch_alter_table('product_sku') as batch_op:
        # E-commerce and marketing
        batch_op.add_column(sa.Column('description', sa.Text, nullable=True))
        batch_op.add_column(sa.Column('image_url', sa.String(512), nullable=True))
        batch_op.add_column(sa.Column('image_path', sa.String(512), nullable=True))
        
        # Physical properties
        batch_op.add_column(sa.Column('weight', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('length', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('width', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('height', sa.Float, nullable=True))
        
        # Retail and POS integration
        batch_op.add_column(sa.Column('barcode', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('upc', sa.String(128), nullable=True))
        
        # Supplier information
        batch_op.add_column(sa.Column('supplier_name', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('supplier_sku', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('supplier_contact', sa.String(256), nullable=True))
        
        # Categorization
        batch_op.add_column(sa.Column('tags', sa.Text, nullable=True))
        batch_op.add_column(sa.Column('category', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('subcategory', sa.String(128), nullable=True))
        
        # Business rules
        batch_op.add_column(sa.Column('minimum_order_quantity', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('maximum_order_quantity', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('profit_margin_target', sa.Float, nullable=True))
        
        # Inventory management
        batch_op.add_column(sa.Column('reserved_quantity', sa.Float, default=0.0))
        batch_op.add_column(sa.Column('available_quantity', sa.Float, default=0.0))
        batch_op.add_column(sa.Column('last_sold_date', sa.DateTime, nullable=True))
        
        # Status flags
        batch_op.add_column(sa.Column('is_discontinued', sa.Boolean, default=False))
        batch_op.add_column(sa.Column('is_hazardous', sa.Boolean, default=False))
        batch_op.add_column(sa.Column('requires_refrigeration', sa.Boolean, default=False))
        
        # Quality control
        batch_op.add_column(sa.Column('quality_status', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('quality_checked_at', sa.DateTime, nullable=True))
        batch_op.add_column(sa.Column('quality_checked_by', sa.Integer, nullable=True))
        
        # Compliance and regulatory
        batch_op.add_column(sa.Column('lot_number', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('batch_number', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('compliance_status', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('regulatory_notes', sa.Text, nullable=True))
        
        # Multi-location tracking
        batch_op.add_column(sa.Column('location_id', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('location_name', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('temperature_at_time', sa.Float, nullable=True))
        
        # Marketplace integration
        batch_op.add_column(sa.Column('shopify_product_id', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('shopify_variant_id', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('etsy_listing_id', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('amazon_asin', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('marketplace_sync_status', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('marketplace_last_sync', sa.DateTime, nullable=True))
        
        # Add foreign key constraints
        batch_op.create_foreign_key(
            'fk_product_sku_quality_checked_by', 'user', ['quality_checked_by'], ['id']
        )
    
    # Add corresponding fields to ProductSKUHistory
    with op.batch_alter_table('product_sku_history') as batch_op:
        # Additional tracking fields
        batch_op.add_column(sa.Column('batch_number', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('lot_number', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('temperature_at_time', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('location_id', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('location_name', sa.String(128), nullable=True))
        
        # Quality and compliance tracking
        batch_op.add_column(sa.Column('quality_status', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('compliance_status', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('quality_checked_by', sa.Integer, nullable=True))
        
        # Marketplace tracking
        batch_op.add_column(sa.Column('marketplace_order_id', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('marketplace_source', sa.String(32), nullable=True))
        
        # Reserved quantity tracking
        batch_op.add_column(sa.Column('reserved_quantity_change', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('old_reserved_quantity', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('new_reserved_quantity', sa.Float, nullable=True))
        
        # Add foreign key constraint
        batch_op.create_foreign_key(
            'fk_product_sku_history_quality_checked_by', 'user', ['quality_checked_by'], ['id']
        )
    
    # Create new indexes for ProductSKU
    op.create_index('idx_barcode_unique', 'product_sku', ['barcode'], unique=True)
    op.create_index('idx_upc_unique', 'product_sku', ['upc'], unique=True)
    op.create_index('idx_category', 'product_sku', ['category', 'subcategory'])
    op.create_index('idx_supplier', 'product_sku', ['supplier_name'])
    op.create_index('idx_quality_status', 'product_sku', ['quality_status'])
    op.create_index('idx_compliance_status', 'product_sku', ['compliance_status'])
    op.create_index('idx_marketplace_sync', 'product_sku', ['marketplace_sync_status'])
    op.create_index('idx_location', 'product_sku', ['location_id'])
    op.create_index('idx_discontinued', 'product_sku', ['is_discontinued'])
    
    # Create new indexes for ProductSKUHistory
    op.create_index('idx_batch_lot', 'product_sku_history', ['batch_number', 'lot_number'])
    op.create_index('idx_location_time', 'product_sku_history', ['location_id', 'timestamp'])
    op.create_index('idx_quality_compliance', 'product_sku_history', ['quality_status', 'compliance_status'])
    op.create_index('idx_marketplace_order', 'product_sku_history', ['marketplace_source', 'marketplace_order_id'])

def downgrade():
    # Drop indexes first
    op.drop_index('idx_marketplace_order', 'product_sku_history')
    op.drop_index('idx_quality_compliance', 'product_sku_history')
    op.drop_index('idx_location_time', 'product_sku_history')
    op.drop_index('idx_batch_lot', 'product_sku_history')
    
    op.drop_index('idx_discontinued', 'product_sku')
    op.drop_index('idx_location', 'product_sku')
    op.drop_index('idx_marketplace_sync', 'product_sku')
    op.drop_index('idx_compliance_status', 'product_sku')
    op.drop_index('idx_quality_status', 'product_sku')
    op.drop_index('idx_supplier', 'product_sku')
    op.drop_index('idx_category', 'product_sku')
    op.drop_index('idx_upc_unique', 'product_sku')
    op.drop_index('idx_barcode_unique', 'product_sku')
    
    # Remove columns from ProductSKUHistory
    with op.batch_alter_table('product_sku_history') as batch_op:
        batch_op.drop_constraint('fk_product_sku_history_quality_checked_by', type_='foreignkey')
        batch_op.drop_column('new_reserved_quantity')
        batch_op.drop_column('old_reserved_quantity')
        batch_op.drop_column('reserved_quantity_change')
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
    
    # Remove columns from ProductSKU
    with op.batch_alter_table('product_sku') as batch_op:
        batch_op.drop_constraint('fk_product_sku_quality_checked_by', type_='foreignkey')
        batch_op.drop_column('marketplace_last_sync')
        batch_op.drop_column('marketplace_sync_status')
        batch_op.drop_column('amazon_asin')
        batch_op.drop_column('etsy_listing_id')
        batch_op.drop_column('shopify_variant_id')
        batch_op.drop_column('shopify_product_id')
        batch_op.drop_column('temperature_at_time')
        batch_op.drop_column('location_name')
        batch_op.drop_column('location_id')
        batch_op.drop_column('regulatory_notes')
        batch_op.drop_column('compliance_status')
        batch_op.drop_column('batch_number')
        batch_op.drop_column('lot_number')
        batch_op.drop_column('quality_checked_by')
        batch_op.drop_column('quality_checked_at')
        batch_op.drop_column('quality_status')
        batch_op.drop_column('requires_refrigeration')
        batch_op.drop_column('is_hazardous')
        batch_op.drop_column('is_discontinued')
        batch_op.drop_column('last_sold_date')
        batch_op.drop_column('available_quantity')
        batch_op.drop_column('reserved_quantity')
        batch_op.drop_column('profit_margin_target')
        batch_op.drop_column('maximum_order_quantity')
        batch_op.drop_column('minimum_order_quantity')
        batch_op.drop_column('subcategory')
        batch_op.drop_column('category')
        batch_op.drop_column('tags')
        batch_op.drop_column('supplier_contact')
        batch_op.drop_column('supplier_sku')
        batch_op.drop_column('supplier_name')
        batch_op.drop_column('upc')
        batch_op.drop_column('barcode')
        batch_op.drop_column('height')
        batch_op.drop_column('width')
        batch_op.drop_column('length')
        batch_op.drop_column('weight')
        batch_op.drop_column('image_path')
        batch_op.drop_column('image_url')
        batch_op.drop_column('description')
