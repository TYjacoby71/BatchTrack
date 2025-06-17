
from datetime import datetime
from ..extensions import db

class IngredientCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    symbol = db.Column(db.String(8), nullable=False)
    type = db.Column(db.String(16), nullable=False)  # weight, volume, count
    base_unit = db.Column(db.String(32))
    conversion_factor = db.Column(db.Float)
    is_custom = db.Column(db.Boolean, default=False)
    is_mapped = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CustomUnitMapping(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    custom_unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=False)
    known_unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=False)
    multiplier = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(32), nullable=False)
    type = db.Column(db.String(32), default='ingredient')
    cost_per_unit = db.Column(db.Float, default=0.0)
    low_stock_threshold = db.Column(db.Float, default=0.0)
    is_perishable = db.Column(db.Boolean, default=False)
    category_id = db.Column(db.Integer, db.ForeignKey('ingredient_category.id'))
    density = db.Column(db.Float)
    storage_amount = db.Column(db.Float, default=0.0)
    storage_unit = db.Column(db.String(32), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    category = db.relationship('IngredientCategory', backref='items')

class InventoryHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    change_type = db.Column(db.String(32), nullable=False)  # restock, use, adjust, waste
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    remaining_quantity = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float, default=0.0)
    note = db.Column(db.Text)
    quantity_used = db.Column(db.Float, default=0.0)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    inventory_item = db.relationship('InventoryItem', backref='history')
    creator = db.relationship('User', backref='inventory_changes')
