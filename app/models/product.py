
from datetime import datetime
from ..extensions import db

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    product_type = db.Column(db.String(32), default='finished')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProductVariation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    size = db.Column(db.String(32))
    size_unit = db.Column(db.String(16))
    price = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', backref='variations')

class ProductInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_variation_id = db.Column(db.Integer, db.ForeignKey('product_variation.id'), nullable=False)
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(32), nullable=False)
    low_stock_threshold = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    product_variation = db.relationship('ProductVariation', backref='inventory')

class ProductEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_variation_id = db.Column(db.Integer, db.ForeignKey('product_variation.id'), nullable=False)
    event_type = db.Column(db.String(32), nullable=False)  # production, sale, adjustment
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    note = db.Column(db.Text)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product_variation = db.relationship('ProductVariation', backref='events')
    batch = db.relationship('Batch', backref='product_events')
    creator = db.relationship('User', backref='product_events')

class ProductInventoryHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_inventory_id = db.Column(db.Integer, db.ForeignKey('product_inventory.id'), nullable=False)
    change_type = db.Column(db.String(32), nullable=False)
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    remaining_quantity = db.Column(db.Float, nullable=False)
    note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product_inventory = db.relationship('ProductInventory', backref='history')
    creator = db.relationship('User', backref='product_inventory_changes')
