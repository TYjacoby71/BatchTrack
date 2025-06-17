
from datetime import datetime
from ..extensions import db

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    base_yield = db.Column(db.Float, nullable=False)
    base_yield_unit = db.Column(db.String(32), nullable=False)
    output_type = db.Column(db.String(32), default='intermediate')  # intermediate, product
    allowed_containers = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RecipeIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    recipe = db.relationship('Recipe', backref='ingredients')
    inventory_item = db.relationship('InventoryItem', backref='used_in_recipes')
