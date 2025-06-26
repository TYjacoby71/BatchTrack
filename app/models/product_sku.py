
from datetime import datetime
from ..extensions import db

class ProductSKU(db.Model):
    """SINGLE PRODUCT TABLE - Contains all product, variant, and inventory data"""
    __tablename__ = 'product_sku'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # CORE PRODUCT INFO (from Product table)
    product_name = db.Column(db.String(128), nullable=False)  # Product name
    product_base_unit = db.Column(db.String(32), nullable=False)  # Base unit for this product line
    
    # VARIANT INFO (from ProductVariation table)
    variant_name = db.Column(db.String(128), nullable=False)  # 'Base', '2oz', '4oz', 'Trial Size', etc.
    variant_description = db.Column(db.Text)  # Optional variant description
    
    # SKU SPECIFIC INFO
    size_label = db.Column(db.String(128), nullable=False)   # Packaging/size info
    unit = db.Column(db.String(32), nullable=False)          # Unit for this specific SKU
    sku_code = db.Column(db.String(128), unique=True, nullable=True)  # Optional custom SKU code
    
    # INVENTORY DATA (from ProductInventory)
    current_quantity = db.Column(db.Float, default=0.0)  # Current stock level
    low_stock_threshold = db.Column(db.Float, default=0)  # Alert threshold
    
    # COST AND PRICING
    unit_cost = db.Column(db.Float, nullable=True)  # Cost per unit
    
    # FIFO AND BATCH TRACKING
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)  # Source batch
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)  # Container type
    
    # EXPIRATION TRACKING
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)
    
    # STATUS AND CONTROLS
    is_active = db.Column(db.Boolean, default=True)  # SKU is active
    is_product_active = db.Column(db.Boolean, default=True)  # Product line is active
    
    # METADATA
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # NOTES AND TRACKING
    notes = db.Column(db.Text, nullable=True)
    
    # COMPUTED PROPERTIES
    @property
    def display_name(self):
        """Human-readable SKU name"""
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
    
    # RELATIONSHIPS
    batch = db.relationship('Batch', backref='product_skus')
    container = db.relationship('InventoryItem', foreign_keys=[container_id])
    
    # Table constraints
    __table_args__ = (
        db.UniqueConstraint('product_name', 'variant_name', 'size_label', name='unique_sku_combination'),
        db.Index('idx_product_name', 'product_name'),
        db.Index('idx_variant_name', 'variant_name'),
        db.Index('idx_active_skus', 'is_active', 'is_product_active'),
    )
    
    def __repr__(self):
        return f'<ProductSKU {self.display_name}>'

class ProductSKUHistory(db.Model):
    """FIFO-enabled history table for SKU changes - mirrors InventoryHistory"""
    __tablename__ = 'product_sku_history'
    
    id = db.Column(db.Integer, primary_key=True)
    sku_id = db.Column(db.Integer, db.ForeignKey('product_sku.id'), nullable=False)
    
    # Change tracking
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(32), nullable=False)  # addition, deduction, recount, sale, spoil, etc.
    quantity_change = db.Column(db.Float, nullable=False)  # +/- amount
    old_quantity = db.Column(db.Float, nullable=False)  # Quantity before change
    new_quantity = db.Column(db.Float, nullable=False)  # Quantity after change
    
    # FIFO tracking (like InventoryHistory)
    remaining_quantity = db.Column(db.Float, default=0.0)  # For FIFO entries
    original_quantity = db.Column(db.Float, nullable=True)  # Original amount added
    unit = db.Column(db.String(32), nullable=False)  # Unit for this entry
    
    # Transaction details
    unit_cost = db.Column(db.Float, nullable=True)
    sale_price = db.Column(db.Float, nullable=True)  # For sales
    customer = db.Column(db.String(128), nullable=True)  # For sales
    
    # FIFO metadata
    fifo_code = db.Column(db.String(64), nullable=True)  # FIFO tracking code
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)
    
    # Expiration tracking
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)
    
    # Source information
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    sku = db.relationship('ProductSKU', backref='history_entries')
    batch = db.relationship('Batch')
    user = db.relationship('User')
    container = db.relationship('InventoryItem', foreign_keys=[container_id])
    
    # Indexes for FIFO performance
    __table_args__ = (
        db.Index('idx_sku_remaining', 'sku_id', 'remaining_quantity'),
        db.Index('idx_sku_timestamp', 'sku_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f'<ProductSKUHistory {self.change_type}: {self.quantity_change}>'
