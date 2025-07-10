
from datetime import datetime
from flask_login import current_user
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

class Product(ScopedModelMixin, db.Model):
    """Main Product model - represents the parent product"""
    __tablename__ = 'product'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Base unit that all variants inherit
    base_unit = db.Column(db.String(32), nullable=False, default='g')
    
    # Product-level settings
    category = db.Column(db.String(64), nullable=True)
    subcategory = db.Column(db.String(64), nullable=True)
    tags = db.Column(db.Text, nullable=True)
    low_stock_threshold = db.Column(db.Float, default=10.0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_discontinued = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Marketplace integration (product-level)
    shopify_product_id = db.Column(db.String(64), nullable=True)
    etsy_shop_section_id = db.Column(db.String(64), nullable=True)
    
    # Relationships
    variants = db.relationship('ProductVariant', back_populates='product', lazy='dynamic', cascade='all, delete-orphan')
    skus = db.relationship('ProductSKU', back_populates='product', lazy='dynamic', cascade='all, delete-orphan')
    
    # Unique constraint on name per organization
    __table_args__ = (
        db.UniqueConstraint('name', 'organization_id', name='unique_product_name_per_org'),
    )
    
    @property
    def base_variant(self):
        """Get the base variant for this product"""
        return self.variants.filter_by(name='Base').first()
    
    @property
    def variant_count(self):
        """Number of active variants"""
        return self.variants.filter_by(is_active=True).count()
    
    def __repr__(self):
        return f'<Product {self.name}>'

class ProductVariant(ScopedModelMixin, db.Model):
    """Product Variant model - represents variations of a product"""
    __tablename__ = 'product_variant'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Variant-specific properties
    color = db.Column(db.String(32), nullable=True)
    material = db.Column(db.String(64), nullable=True)
    scent = db.Column(db.String(64), nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    product = db.relationship('Product', back_populates='variants')
    skus = db.relationship('ProductSKU', back_populates='variant', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def bulk_sku(self):
        """Get the bulk SKU for this variant"""
        return self.skus.filter_by(size_label='Bulk').first()
    
    # Unique constraint on product + variant name
    __table_args__ = (
        db.UniqueConstraint('product_id', 'name', name='unique_product_variant'),
    )
    
    def __repr__(self):
        return f'<ProductVariant {self.product.name} - {self.name}>'

class ProductSKU(ScopedModelMixin, db.Model):
    """Product SKU model - represents sellable units of inventory"""
    __tablename__ = 'product_sku'
    
    # INVENTORY ITEM REFERENCE - unified inventory control (PRIMARY KEY)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), primary_key=True)
    
    # CORE PRODUCT IDENTIFICATION
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variant.id'), nullable=False)
    size_label = db.Column(db.String(64), nullable=False, default='Bulk')
    sku_code = db.Column(db.String(64), unique=True, nullable=False)
    sku_name = db.Column(db.String(128), nullable=True)
    
    # LEGACY FIELDS FOR COMPATIBILITY (will be calculated from inventory_item)
    unit = db.Column(db.String(32), nullable=False)
    low_stock_threshold = db.Column(db.Float, default=10.0)
    
    # FIFO REFERENCE
    fifo_id = db.Column(db.String(32), nullable=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)
    
    # PRICING - cost comes from inventory_item.cost_per_unit
    retail_price = db.Column(db.Float, nullable=True)
    wholesale_price = db.Column(db.Float, nullable=True)
    profit_margin_target = db.Column(db.Float, nullable=True)
    
    # CATEGORIZATION
    category = db.Column(db.String(64), nullable=True)
    subcategory = db.Column(db.String(64), nullable=True)
    tags = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    
    # STATUS
    is_active = db.Column(db.Boolean, default=True)
    is_product_active = db.Column(db.Boolean, default=True)
    is_discontinued = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # SUPPLIER AND SOURCING
    supplier_name = db.Column(db.String(128), nullable=True)
    supplier_sku = db.Column(db.String(64), nullable=True)
    supplier_cost = db.Column(db.Float, nullable=True)
    
    # PHYSICAL PROPERTIES
    weight = db.Column(db.Float, nullable=True)
    weight_unit = db.Column(db.String(16), nullable=True)
    dimensions = db.Column(db.String(64), nullable=True)
    
    # BARCODES
    barcode = db.Column(db.String(128), nullable=True, unique=True)
    upc = db.Column(db.String(32), nullable=True, unique=True)
    
    # QUALITY CONTROL
    quality_status = db.Column(db.String(32), nullable=True)
    compliance_status = db.Column(db.String(32), nullable=True)
    quality_checked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    quality_checked_at = db.Column(db.DateTime, nullable=True)
    
    # STORAGE
    location_id = db.Column(db.String(128), nullable=True)
    location_name = db.Column(db.String(128), nullable=True)
    temperature_at_time = db.Column(db.Float, nullable=True)
    
    # MARKETPLACE INTEGRATION
    shopify_product_id = db.Column(db.String(64), nullable=True)
    shopify_variant_id = db.Column(db.String(64), nullable=True)
    etsy_listing_id = db.Column(db.String(64), nullable=True)
    amazon_asin = db.Column(db.String(64), nullable=True)
    marketplace_sync_status = db.Column(db.String(32), nullable=True)
    marketplace_last_sync = db.Column(db.DateTime, nullable=True)
    
    # EXPIRATION TRACKING
    expiration_date = db.Column(db.DateTime, nullable=True)
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    
    # COMPUTED PROPERTIES
    @property
    def display_name(self):
        """Human-readable SKU name"""
        if self.sku_name:
            return self.sku_name
        return f"{self.product.name} - {self.variant.name} - {self.size_label}"
    
    @property
    def product_name(self):
        """Legacy compatibility - get product name"""
        return self.product.name if self.product else None
    
    @property
    def variant_name(self):
        """Legacy compatibility - get variant name"""
        return self.variant.name if self.variant else None
    
    @property
    def product_base_unit(self):
        """Get the base unit from the parent product"""
        return self.product.base_unit if self.product else self.unit
    
    @property
    def quantity(self):
        """Get current quantity from unified inventory"""
        return self.inventory_item.quantity if self.inventory_item else 0.0
    
    @property
    def cost_per_unit(self):
        """Get cost per unit from unified inventory"""
        return self.inventory_item.cost_per_unit if self.inventory_item else 0.0
    
    @property
    def reserved_quantity(self):
        """Reserved quantity - for compatibility"""
        # This could be calculated from ProductSKUHistory if needed
        return 0.0
    
    @property
    def is_low_stock(self):
        """Check if current stock is below threshold"""
        return self.quantity <= self.low_stock_threshold
    
    @property
    def stock_status(self):
        """Get stock status string"""
        if self.quantity == 0:
            return "Out of Stock"
        elif self.is_low_stock:
            return "Low Stock"
        else:
            return "In Stock"
    
    @property
    def available_for_sale(self):
        """Calculate available quantity for sale"""
        current_qty = self.inventory_item.quantity if self.inventory_item else 0.0
        return max(0, current_qty - (self.reserved_quantity or 0))
    
    # RELATIONSHIPS
    product = db.relationship('Product', back_populates='skus')
    variant = db.relationship('ProductVariant', back_populates='skus')
    inventory_item = db.relationship('InventoryItem', foreign_keys=[inventory_item_id], backref='product_sku')
    batch = db.relationship('Batch', foreign_keys=[batch_id], backref='source_product_skus')
    container = db.relationship('InventoryItem', foreign_keys=[container_id])
    quality_checker = db.relationship('User', foreign_keys=[quality_checked_by])
    
    # Data integrity validation
    def validate_product_variant_consistency(self):
        """Ensure product_id matches variant.product_id for data integrity"""
        if self.variant and self.product_id != self.variant.product_id:
            raise ValueError(f"SKU product_id ({self.product_id}) does not match variant's product_id ({self.variant.product_id})")
    
    # Table constraints
    __table_args__ = (
        db.UniqueConstraint('product_id', 'variant_id', 'size_label', 'fifo_id', name='unique_sku_combination'),
        db.UniqueConstraint('barcode', name='unique_barcode'),
        db.UniqueConstraint('upc', name='unique_upc'),
        db.Index('idx_product_variant', 'product_id', 'variant_id'),
        db.Index('idx_active_skus', 'is_active', 'is_product_active'),
        db.Index('idx_inventory_item', 'inventory_item_id'),
    )
    
    @property
    def display_name(self):
        """Get display name for the SKU"""
        if self.sku_name:
            return self.sku_name
        elif self.product and self.variant:
            return f"{self.product.name} - {self.variant.name} - {self.size_label}"
        else:
            return self.sku_code or f"SKU #{self.id}"
    
    @classmethod
    def generate_sku_code(cls, product_name, variant_name, size_label):
        """Generate a standardized SKU code from product/variant/size"""
        # Create slugs from names
        product_slug = ''.join(c.upper() if c.isalnum() else '' for c in product_name)[:8]
        variant_slug = ''.join(c.upper() if c.isalnum() else '' for c in variant_name)[:6]
        size_slug = ''.join(c.upper() if c.isalnum() else '' for c in size_label)[:6]
        
        return f"{product_slug}-{variant_slug}-{size_slug}"
    
    def __repr__(self):
        return f'<ProductSKU {self.display_name}>'

class ProductSKUHistory(ScopedModelMixin, db.Model):
    """FIFO-enabled history table for SKU changes"""
    __tablename__ = 'product_sku_history'
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    
    # Change tracking
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(32), nullable=False)
    quantity_change = db.Column(db.Float, nullable=False)
    
    # FIFO tracking
    remaining_quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(32), nullable=False)
    
    # Transaction details
    unit_cost = db.Column(db.Float, nullable=True)
    sale_price = db.Column(db.Float, nullable=True)
    customer = db.Column(db.String(128), nullable=True)
    
    # FIFO metadata
    fifo_code = db.Column(db.String(64), nullable=True)
    fifo_reference_id = db.Column(db.Integer, db.ForeignKey('product_sku_history.id'), nullable=True)
    fifo_source = db.Column(db.String(128), nullable=True)
    
    # Expiration tracking
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)
    
    # Source information
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # POS integration
    order_id = db.Column(db.String(64), nullable=True)
    reservation_id = db.Column(db.String(64), nullable=True)
    is_reserved = db.Column(db.Boolean, default=False)
    sale_location = db.Column(db.String(64), nullable=True)
    
    # Additional tracking
    quantity_used = db.Column(db.Float, default=0.0)
    batch_number = db.Column(db.String(128), nullable=True)
    lot_number = db.Column(db.String(128), nullable=True)
    temperature_at_time = db.Column(db.Float, nullable=True)
    location_id = db.Column(db.String(128), nullable=True)
    location_name = db.Column(db.String(128), nullable=True)
    
    # Quality and compliance
    quality_status = db.Column(db.String(32), nullable=True)
    compliance_status = db.Column(db.String(32), nullable=True)
    quality_checked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Marketplace tracking
    marketplace_order_id = db.Column(db.String(128), nullable=True)
    marketplace_source = db.Column(db.String(32), nullable=True)
    
    # Relationships
    inventory_item = db.relationship('InventoryItem', foreign_keys=[inventory_item_id], backref='product_history_entries')
    batch = db.relationship('Batch', foreign_keys=[batch_id])
    container = db.relationship('InventoryItem', foreign_keys=[container_id])
    user = db.relationship('User', foreign_keys=[created_by])
    quality_checker = db.relationship('User', foreign_keys=[quality_checked_by])
    fifo_reference = db.relationship('ProductSKUHistory', remote_side=[id])
    
    # Indexes
    __table_args__ = (
        db.Index('idx_inventory_item_remaining', 'inventory_item_id', 'remaining_quantity'),
        db.Index('idx_inventory_item_timestamp', 'inventory_item_id', 'timestamp'),
        db.Index('idx_change_type', 'change_type'),
        db.Index('idx_fifo_code', 'fifo_code'),
    )
    
    def __repr__(self):
        return f'<ProductSKUHistory {self.change_type}: {self.quantity_change}>'
