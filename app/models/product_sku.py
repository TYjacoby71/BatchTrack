
from datetime import datetime
from flask_login import current_user
from ..extensions import db
from .mixins import ScopedModelMixin

class ProductSKU(ScopedModelMixin, db.Model):
    """Product SKU model - represents sellable units of inventory"""
    __tablename__ = 'product_sku'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # CORE PRODUCT IDENTIFICATION - Now using foreign keys
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variant.id'), nullable=False)
    size_label = db.Column(db.String(64), nullable=False, default='Bulk')
    sku_code = db.Column(db.String(64), unique=True, nullable=False)
    sku_name = db.Column(db.String(128), nullable=True)  # Optional human-readable name override
    
    # LEGACY FIELDS - Keep for backward compatibility during migration
    product_name = db.Column(db.String(128), nullable=True)  # Will be removed after migration
    variant_name = db.Column(db.String(128), nullable=True)  # Will be removed after migration
    
    # INVENTORY TRACKING - SINGLE SOURCE OF TRUTH
    current_quantity = db.Column(db.Float, default=0.0)  # Sum of all history entries
    reserved_quantity = db.Column(db.Float, default=0.0)  # Reserved for orders
    unit = db.Column(db.String(32), nullable=False)
    low_stock_threshold = db.Column(db.Float, default=10.0)
    
    # FIFO REFERENCE - LINKS TO BATCH/INVENTORY ORIGIN
    fifo_id = db.Column(db.String(32), nullable=True)  # Links to raw inventory FIFO
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)
    
    # PRICING
    unit_cost = db.Column(db.Float, nullable=True)
    retail_price = db.Column(db.Float, nullable=True)
    wholesale_price = db.Column(db.Float, nullable=True)
    profit_margin_target = db.Column(db.Float, nullable=True)  # Target percentage
    
    # PRODUCT CATEGORIZATION
    category = db.Column(db.String(64), nullable=True)
    subcategory = db.Column(db.String(64), nullable=True)
    tags = db.Column(db.Text, nullable=True)  # JSON or comma-separated
    description = db.Column(db.Text, nullable=True)
    
    # PRODUCT STATUS
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
    dimensions = db.Column(db.String(64), nullable=True)  # "L x W x H"
    
    # BARCODES
    barcode = db.Column(db.String(128), nullable=True, unique=True)
    upc = db.Column(db.String(32), nullable=True, unique=True)
    
    # QUALITY CONTROL
    quality_status = db.Column(db.String(32), nullable=True)  # passed, failed, pending, quarantine
    compliance_status = db.Column(db.String(32), nullable=True)  # compliant, non_compliant, pending
    quality_checked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    quality_checked_at = db.Column(db.DateTime, nullable=True)
    
    # STORAGE
    location_id = db.Column(db.String(128), nullable=True)  # Storage location identifier
    location_name = db.Column(db.String(128), nullable=True)  # Human-readable location
    temperature_at_time = db.Column(db.Float, nullable=True)  # Storage temperature when last recorded
    
    # MARKETPLACE INTEGRATION
    shopify_product_id = db.Column(db.String(64), nullable=True)
    shopify_variant_id = db.Column(db.String(64), nullable=True)
    etsy_listing_id = db.Column(db.String(64), nullable=True)
    amazon_asin = db.Column(db.String(64), nullable=True)
    marketplace_sync_status = db.Column(db.String(32), nullable=True)  # synced, pending, error
    marketplace_last_sync = db.Column(db.DateTime, nullable=True)
    
    # COMPUTED PROPERTIES
    @property
    def display_name(self):
        """Human-readable SKU name"""
        if self.sku_name:
            return self.sku_name
        # Use relationships if available, fall back to legacy fields
        product_name = self.product.name if self.product else self.product_name
        variant_name = self.variant.name if self.variant else self.variant_name
        return f"{product_name} - {variant_name} - {self.size_label}"
    
    @property
    def product_base_unit(self):
        """Get the base unit from the parent product"""
        return self.product.base_unit if self.product else self.unit
    
    @property
    def is_low_stock(self):
        """Check if current stock is below threshold"""
        return self.current_quantity <= self.low_stock_threshold
    
    @property
    def stock_status(self):
        """Get stock status string"""
        if self.current_quantity == 0:
            return "Out of Stock"
        elif self.is_low_stock:
            return "Low Stock"
        else:
            return "In Stock"
    
    @property
    def profit_margin(self):
        """Calculate profit margin if both cost and retail price are set"""
        if self.unit_cost and self.retail_price and self.unit_cost > 0:
            return ((self.retail_price - self.unit_cost) / self.retail_price) * 100
        return self.profit_margin_target  # Fall back to target if actual can't be calculated
    
    @property
    def available_for_sale(self):
        """Calculate available quantity for sale (current - reserved)"""
        return max(0, self.current_quantity - (self.reserved_quantity or 0))
    
    @property
    def is_marketplace_synced(self):
        """Check if product is synced with any marketplace"""
        return any([self.shopify_product_id, self.etsy_listing_id, self.amazon_asin])
    
    @property
    def compliance_status_display(self):
        """Human-readable compliance status"""
        status_map = {
            'compliant': 'Compliant',
            'non_compliant': 'Non-Compliant',
            'pending': 'Pending Review',
            None: 'Not Reviewed'
        }
        return status_map.get(self.compliance_status, 'Unknown')
    
    @property
    def quality_status_display(self):
        """Human-readable quality status"""
        status_map = {
            'passed': 'Quality Passed',
            'failed': 'Quality Failed', 
            'pending': 'Quality Pending',
            'quarantine': 'Quarantined',
            None: 'Not Tested'
        }
        return status_map.get(self.quality_status, 'Unknown')
    
    # RELATIONSHIPS
    batch = db.relationship('Batch', foreign_keys=[batch_id], backref='source_product_skus')
    container = db.relationship('InventoryItem', foreign_keys=[container_id])
    quality_checker = db.relationship('User', foreign_keys=[quality_checked_by])
    
    # Table constraints
    __table_args__ = (
        db.UniqueConstraint('product_id', 'variant_id', 'size_label', 'fifo_id', name='unique_sku_fifo_combination'),
        db.UniqueConstraint('barcode', name='unique_barcode'),
        db.UniqueConstraint('upc', name='unique_upc'),
        db.Index('idx_product_variant', 'product_id', 'variant_id'),
        db.Index('idx_active_skus', 'is_active', 'is_product_active'),
        db.Index('idx_batch_fifo', 'batch_id', 'fifo_id'),
        db.Index('idx_low_stock', 'current_quantity', 'low_stock_threshold'),
        db.Index('idx_current_reserved_qty', 'current_quantity', 'reserved_quantity'),
        db.Index('idx_category', 'category', 'subcategory'),
        db.Index('idx_supplier', 'supplier_name'),
        db.Index('idx_quality_status', 'quality_status'),
        db.Index('idx_compliance_status', 'compliance_status'),
        db.Index('idx_marketplace_sync', 'marketplace_sync_status'),
        db.Index('idx_location', 'location_id'),
        db.Index('idx_discontinued', 'is_discontinued'),
        # Legacy indexes for backward compatibility
        db.Index('idx_legacy_product_name', 'product_name'),
        db.Index('idx_legacy_variant_name', 'variant_name'),
    )
    
    def __repr__(self):
        return f'<ProductSKU {self.display_name}>'

class ProductSKUHistory(ScopedModelMixin, db.Model):
    """FIFO-enabled history table for SKU changes - mirrors InventoryHistory"""
    __tablename__ = 'product_sku_history'
    
    id = db.Column(db.Integer, primary_key=True)
    sku_id = db.Column(db.Integer, db.ForeignKey('product_sku.id'), nullable=False)
    
    # Change tracking
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(32), nullable=False)  # batch_addition, recount, spoil, sale, trash, damage, gift/tester, manual_add
    quantity_change = db.Column(db.Float, nullable=False)  # +/- amount - THIS IS THE DELTA
    
    # FIFO tracking - ESSENTIAL FIELDS ONLY
    remaining_quantity = db.Column(db.Float, default=0.0)  # For FIFO tracking on deductions
    original_quantity = db.Column(db.Float, nullable=True)  # Only set for additions - starting FIFO amount
    unit = db.Column(db.String(32), nullable=False)  # Unit for this entry
    
    # Transaction details
    unit_cost = db.Column(db.Float, nullable=True)  # Cost per unit at time of event
    sale_price = db.Column(db.Float, nullable=True)  # For sales
    customer = db.Column(db.String(128), nullable=True)  # For sales
    
    # FIFO metadata
    fifo_code = db.Column(db.String(64), nullable=True)  # FIFO tracking code
    fifo_reference_id = db.Column(db.Integer, db.ForeignKey('product_sku_history.id'), nullable=True)  # Reference to parent FIFO entry
    fifo_source = db.Column(db.String(128), nullable=True)  # FIFO source identifier - batch label or fifo code
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)
    
    # Expiration tracking
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)
    
    # Source information
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Additional tracking fields to match InventoryHistory
    quantity_used = db.Column(db.Float, default=0.0)  # Track actual consumption vs deduction
    
    # POS integration fields
    order_id = db.Column(db.String(64), nullable=True)  # External order ID (Shopify, etc.) 
    reservation_id = db.Column(db.String(64), nullable=True)  # For reserving stock
    is_reserved = db.Column(db.Boolean, default=False)  # Track if quantity is reserved
    sale_location = db.Column(db.String(64), nullable=True)  # manual, shopify, etsy, amazon, etc.
    
    # Additional metadata
    note = db.Column(db.Text, nullable=True)  # Mirror InventoryHistory field name
    
    # ADDITIONAL TRACKING FIELDS
    batch_number = db.Column(db.String(128), nullable=True)  # Text batch identifier 
    lot_number = db.Column(db.String(128), nullable=True)  # Regulatory lot number
    temperature_at_time = db.Column(db.Float, nullable=True)  # Temperature when change occurred
    location_id = db.Column(db.String(128), nullable=True)  # Location when change occurred
    location_name = db.Column(db.String(128), nullable=True)  # Human-readable location
    
    # QUALITY AND COMPLIANCE TRACKING
    quality_status = db.Column(db.String(32), nullable=True)  # Quality status at time of change
    compliance_status = db.Column(db.String(32), nullable=True)  # Compliance status at time of change
    quality_checked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # MARKETPLACE TRACKING
    marketplace_order_id = db.Column(db.String(128), nullable=True)  # Order ID from marketplace
    marketplace_source = db.Column(db.String(32), nullable=True)  # shopify, etsy, amazon, etc.
    
    # Reserved quantity changes are tracked in the main SKU table only
    
    # Relationships
    sku = db.relationship('ProductSKU', backref='history_entries')
    batch = db.relationship('Batch', foreign_keys=[batch_id])
    user = db.relationship('User', foreign_keys=[created_by])
    quality_checker = db.relationship('User', foreign_keys=[quality_checked_by])
    container = db.relationship('InventoryItem', foreign_keys=[container_id])
    fifo_reference = db.relationship('ProductSKUHistory', remote_side=[id])
    
    # Indexes for FIFO performance and new fields
    __table_args__ = (
        db.Index('idx_sku_remaining', 'sku_id', 'remaining_quantity'),
        db.Index('idx_sku_timestamp', 'sku_id', 'timestamp'),
        db.Index('idx_change_type', 'change_type'),
        db.Index('idx_fifo_code', 'fifo_code'),
        db.Index('idx_fifo_reference', 'fifo_reference_id'),
        db.Index('idx_fifo_source', 'fifo_source'),
        db.Index('idx_batch_lot', 'batch_number', 'lot_number'),
        db.Index('idx_location_time', 'location_id', 'timestamp'),
        db.Index('idx_quality_compliance', 'quality_status', 'compliance_status'),
        db.Index('idx_marketplace_order', 'marketplace_source', 'marketplace_order_id'),
        db.Index('idx_order_reservation', 'order_id', 'reservation_id'),
        db.Index('idx_sale_location', 'sale_location'),
    )
    
    def __repr__(self):
        return f'<ProductSKUHistory {self.change_type}: {self.quantity_change}>'
