
from datetime import datetime
from ..extensions import db

class ProductSKU(db.Model):
    """SKU as primary entity - like InventoryItem but for products"""
    __tablename__ = 'product_sku'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variation.id'), nullable=False)
    variant_name = db.Column(db.String(128), nullable=False)  # For display
    size_label = db.Column(db.String(128), nullable=False)
    sku_code = db.Column(db.String(128), unique=True, nullable=True)
    unit = db.Column(db.String(32), nullable=False)
    
    # Computed from FIFO entries
    @property
    def current_quantity(self):
        """Sum of all active FIFO entries"""
        return sum(entry.quantity for entry in self.fifo_entries if entry.quantity > 0)
    
    # Settings
    low_stock_threshold = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', backref='skus')
    variant = db.relationship('ProductVariation', backref='skus')
    fifo_entries = db.relationship('ProductInventory', backref='sku_entity', lazy='dynamic')
    history = db.relationship('ProductInventoryHistory', backref='sku_entity', lazy='dynamic')
    
    __table_args__ = (
        db.UniqueConstraint('product_id', 'variant_id', 'size_label', name='unique_sku_combination'),
    )
    
    def __repr__(self):
        return f'<ProductSKU {self.product.name} - {self.variant_name} - {self.size_label}>'
