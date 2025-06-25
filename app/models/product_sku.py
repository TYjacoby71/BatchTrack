
from datetime import datetime
from ..extensions import db

class ProductSKU(db.Model):
    """PRIMARY ENTITY: Single source of truth for all product data"""
    __tablename__ = 'product_sku'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # CORE IDENTITY - Required fields that define this SKU
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variation.id'), nullable=False)
    variant_name = db.Column(db.String(128), nullable=False)  # Cached from variant for performance
    size_label = db.Column(db.String(128), nullable=False)   # Packaging/size info
    unit = db.Column(db.String(32), nullable=False)          # Base unit for this SKU
    
    # UNIQUE IDENTIFIERS
    sku_code = db.Column(db.String(128), unique=True, nullable=True)  # Optional custom SKU code
    
    # INVENTORY SETTINGS - Configured per SKU
    low_stock_threshold = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # COMPUTED PROPERTIES - Never stored, always calculated
    @property
    def current_quantity(self):
        """AUTHORITATIVE quantity - sum of all FIFO entries"""
        return sum(entry.quantity for entry in self.fifo_entries if entry.quantity > 0)
    
    @property
    def display_name(self):
        """Human-readable SKU name"""
        return f"{self.product.name} - {self.variant_name} - {self.size_label}"
    
    @property
    def fifo_count(self):
        """Number of active FIFO entries"""
        return len([e for e in self.fifo_entries if e.quantity > 0])
    
    # METADATA
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # RELATIONSHIPS - One-to-many from SKU (never the reverse)
    product = db.relationship('Product', backref='skus')
    variant = db.relationship('ProductVariation', backref='skus')
    
    # Table constraints
    __table_args__ = (
        db.UniqueConstraint('product_id', 'variant_id', 'size_label', name='unique_sku_combination'),
    )
    
    def __repr__(self):
        return f'<ProductSKU {self.display_name}>'
