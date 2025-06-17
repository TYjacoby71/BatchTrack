
from datetime import datetime
from ..extensions import db

class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    batch_number = db.Column(db.String(32), unique=True, nullable=False)
    status = db.Column(db.String(32), default='planning')  # planning, in_progress, completed, cancelled
    scale_factor = db.Column(db.Float, default=1.0)
    target_yield = db.Column(db.Float)
    target_yield_unit = db.Column(db.String(32))
    actual_yield = db.Column(db.Float)
    actual_yield_unit = db.Column(db.String(32))
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    recipe = db.relationship('Recipe', backref='batches')
    creator = db.relationship('User', backref='created_batches')

class BatchIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    planned_quantity = db.Column(db.Float, nullable=False)
    actual_quantity = db.Column(db.Float)
    unit = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    batch = db.relationship('Batch', backref='ingredients')
    inventory_item = db.relationship('InventoryItem', backref='used_in_batches')

class BatchContainer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    batch = db.relationship('Batch', backref='containers')
    inventory_item = db.relationship('InventoryItem', backref='used_as_containers')

class ExtraBatchContainer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    batch = db.relationship('Batch', backref='extra_containers')
    inventory_item = db.relationship('InventoryItem', backref='used_as_extra_containers')

class BatchTimer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(32), default='pending')  # pending, running, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    batch = db.relationship('Batch', backref='timers')

class ExtraBatchIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    batch = db.relationship('Batch', backref='extra_ingredients')
    inventory_item = db.relationship('InventoryItem', backref='used_as_extra_ingredients')

class BatchInventoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    change_type = db.Column(db.String(32), nullable=False)
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    batch = db.relationship('Batch', backref='inventory_logs')
    inventory_item = db.relationship('InventoryItem', backref='batch_logs')
