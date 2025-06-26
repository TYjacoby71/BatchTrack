

from datetime import datetime
from ..extensions import db
from .mixins import ScopedModelMixin

class ProductSKU(ScopedModelMixin, db.Model):
    """SINGLE PRODUCT TABLE - Contains all product, variant, and inventory data"""
    __tablename__ = 'product_sku'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # CORE PRODUCT INFO (from Product table)
    product_name = db.Column(db.String(128), nullable=False)  # Product name
    product_id = db.Column(db.Integer, nullable=True)  # Legacy product ID for reference
    product_base_unit = db.Column(db.String(32), nullable=False)  # Base unit for this product line
    
    # VARIANT INFO (from ProductVariation table)
    variant_name = db.Column(db.String(128), nullable=False)  # 'Base', '2oz', '4oz', 'Trial Size', etc.
    variant_id = db.Column(db.Integer, nullable=True)  # Legacy variant ID for reference
    variant_description = db.Column(db.Text)  # Optional variant description
    
    # SKU SPECIFIC INFO
    sku_name = db.Column(db.String(128), nullable=True)  # User-added SKU name
    size_label = db.Column(db.String(128), nullable=False)   # Packaging/size info (from container or 'Bulk')
    unit = db.Column(db.String(32), nullable=False)          # Unit for this specific SKU
    sku_code = db.Column(db.String(128), unique=True, nullable=True)  # Optional custom SKU code
    
    # INVENTORY DATA (from ProductInventory)
    current_quantity = db.Column(db.Float, default=0.0)  # Current stock level
    remaining_quantity = db.Column(db.Float, default=0.0)  # For FIFO tracking
    original_quantity = db.Column(db.Float, default=0.0)  # Original amount added
    low_stock_threshold = db.Column(db.Float, default=0)  # Alert threshold for this SKU
    
    # COST AND PRICING
    unit_cost = db.Column(db.Float, nullable=True)  # Cost per unit (ingredients + containers / yield)
    retail_price = db.Column(db.Float, nullable=True)  # Retail price per unit
    
    # FIFO AND BATCH TRACKING
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)  # Source batch
    fifo_id = db.Column(db.String(64), nullable=True)  # FIFO tracking identifier
    change_type = db.Column(db.String(32), default='batch_addition')  # recount, spoil, sale, trash, damage, gift/tester, manual_add, batch_addition
    
    # CONTAINER AND SIZE INFO (from batch)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)  # Container type
    container_size = db.Column(db.String(128), nullable=True)  # Container size(s) used
    container_line_cost = db.Column(db.Float, nullable=True)  # Cost of containers for this SKU
    
    # EXPIRATION TRACKING (from batch)
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)  # Derived from shelf life
    batch_completed_at = db.Column(db.DateTime, nullable=True)  # When batch was completed
    
    # SALES AND CUSTOMER TRACKING
    customer = db.Column(db.String(128), nullable=True)  # Customer name for sales
    
    # STATUS AND CONTROLS
    is_active = db.Column(db.Boolean, default=True)  # SKU is active
    is_product_active = db.Column(db.Boolean, default=True)  # Product line is active
    
    # METADATA (from batch and user data)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # From batch data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # NOTES AND TRACKING
    notes = db.Column(db.Text, nullable=True)
    
    # E-COMMERCE AND MARKETING FIELDS
    description = db.Column(db.Text, nullable=True)  # Product description for marketing
    image_url = db.Column(db.String(512), nullable=True)  # Product image URL
    image_path = db.Column(db.String(512), nullable=True)  # Local image path
    
    # PHYSICAL PROPERTIES
    weight = db.Column(db.Float, nullable=True)  # Weight in grams
    length = db.Column(db.Float, nullable=True)  # Length in cm
    width = db.Column(db.Float, nullable=True)  # Width in cm
    height = db.Column(db.Float, nullable=True)  # Height in cm
    
    # RETAIL AND POS INTEGRATION
    barcode = db.Column(db.String(128), nullable=True)  # Barcode/UPC
    upc = db.Column(db.String(128), nullable=True)  # UPC code
    
    # SUPPLIER INFORMATION
    supplier_name = db.Column(db.String(128), nullable=True)
    supplier_sku = db.Column(db.String(128), nullable=True)
    supplier_contact = db.Column(db.String(256), nullable=True)
    
    # CATEGORIZATION AND ORGANIZATION
    tags = db.Column(db.Text, nullable=True)  # JSON array of tags
    category = db.Column(db.String(128), nullable=True)  # Primary category
    subcategory = db.Column(db.String(128), nullable=True)  # Subcategory
    
    # BUSINESS RULES
    minimum_order_quantity = db.Column(db.Float, nullable=True)
    maximum_order_quantity = db.Column(db.Float, nullable=True)
    profit_margin_target = db.Column(db.Float, nullable=True)  # Target profit margin %
    
    # INVENTORY MANAGEMENT
    reserved_quantity = db.Column(db.Float, default=0.0)  # Reserved for pending orders
    available_quantity = db.Column(db.Float, default=0.0)  # Available = current - reserved
    last_sold_date = db.Column(db.DateTime, nullable=True)  # Last sale date for analytics
    
    # STATUS FLAGS
    is_discontinued = db.Column(db.Boolean, default=False)
    is_hazardous = db.Column(db.Boolean, default=False)
    requires_refrigeration = db.Column(db.Boolean, default=False)
    
    # QUALITY CONTROL
    quality_status = db.Column(db.String(32), nullable=True)  # passed, failed, pending, quarantine
    quality_checked_at = db.Column(db.DateTime, nullable=True)
    quality_checked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # COMPLIANCE AND REGULATORY
    lot_number = db.Column(db.String(128), nullable=True)  # Regulatory lot number
    batch_number = db.Column(db.String(128), nullable=True)  # Text batch identifier
    compliance_status = db.Column(db.String(32), nullable=True)  # compliant, non_compliant, pending
    regulatory_notes = db.Column(db.Text, nullable=True)
    
    # MULTI-LOCATION TRACKING
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
        return f"{self.product_name} - {self.variant_name} - {self.size_label}"
    
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
        db.UniqueConstraint('product_name', 'variant_name', 'size_label', 'fifo_id', name='unique_sku_fifo_combination'),
        db.UniqueConstraint('barcode', name='unique_barcode'),
        db.UniqueConstraint('upc', name='unique_upc'),
        db.Index('idx_product_name', 'product_name'),
        db.Index('idx_variant_name', 'variant_name'),
        db.Index('idx_active_skus', 'is_active', 'is_product_active'),
        db.Index('idx_batch_fifo', 'batch_id', 'fifo_id'),
        db.Index('idx_low_stock', 'current_quantity', 'low_stock_threshold'),
        db.Index('idx_category', 'category', 'subcategory'),
        db.Index('idx_supplier', 'supplier_name'),
        db.Index('idx_quality_status', 'quality_status'),
        db.Index('idx_compliance_status', 'compliance_status'),
        db.Index('idx_marketplace_sync', 'marketplace_sync_status'),
        db.Index('idx_location', 'location_id'),
        db.Index('idx_discontinued', 'is_discontinued'),
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
    quantity_change = db.Column(db.Float, nullable=False)  # +/- amount
    old_quantity = db.Column(db.Float, nullable=False)  # Quantity before change
    new_quantity = db.Column(db.Float, nullable=False)  # Quantity after change
    
    # FIFO tracking (like InventoryHistory)
    remaining_quantity = db.Column(db.Float, default=0.0)  # For FIFO entries
    original_quantity = db.Column(db.Float, nullable=True)  # Original amount added
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
    
    # RESERVED QUANTITY TRACKING
    reserved_quantity_change = db.Column(db.Float, nullable=True)  # Change in reserved quantity
    old_reserved_quantity = db.Column(db.Float, nullable=True)  # Reserved quantity before change
    new_reserved_quantity = db.Column(db.Float, nullable=True)  # Reserved quantity after change
    
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

