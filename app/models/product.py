from datetime import datetime
from flask_login import current_user
from ..extensions import db
from .mixins import ScopedModelMixin

class Product(ScopedModelMixin, db.Model):
    """Main Product model - represents the parent product"""
    __tablename__ = 'product'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
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
    variants = db.relationship('ProductVariant', backref='product', cascade="all, delete-orphan")
    skus = db.relationship('ProductSKU', backref='product', cascade="all, delete-orphan")

    @property
    def base_variant(self):
        """Get the base variant for this product"""
        return self.variants.filter_by(name='Base').first()

    @property
    def total_inventory(self):
        """Total inventory across all SKUs"""
        return sum(sku.current_quantity for sku in self.skus if sku.is_active)

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
    size = db.Column(db.String(32), nullable=True)
    material = db.Column(db.String(64), nullable=True)

    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    skus = db.relationship('ProductSKU', backref='variant', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def bulk_sku(self):
        """Get the bulk SKU for this variant"""
        return self.skus.filter_by(size_label='Bulk').first()

    @property
    def total_inventory(self):
        """Total inventory for this variant across all size labels"""
        return sum(sku.current_quantity for sku in self.skus if sku.is_active)

    # Unique constraint on product + variant name
    __table_args__ = (
        db.UniqueConstraint('product_id', 'name', name='unique_product_variant'),
    )

    def __repr__(self):
        return f'<ProductVariant {self.product.name} - {self.name}>'