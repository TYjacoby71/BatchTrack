from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import current_user, UserMixin
from datetime import date

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(32), default='user')

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

class RecipeIngredient(db.Model):
    __tablename__ = 'recipe_ingredients'
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), primary_key=True)
    amount = db.Column(db.Float)
    unit = db.Column(db.String(32))
    inventory_item = db.relationship('InventoryItem', backref=db.backref('recipe_ingredients', lazy='dynamic'))

class Recipe(db.Model):
    __tablename__ = 'recipe'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    instructions = db.Column(db.Text)
    label_prefix = db.Column(db.String(8))
    qr_image = db.Column(db.String(128))
    parent_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    is_locked = db.Column(db.Boolean, default=False)
    parent = db.relationship('Recipe', remote_side=[id], backref='variations')
    recipe_ingredients = db.relationship('RecipeIngredient', backref='recipe', cascade="all, delete-orphan")

class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer)
    recipe_name = db.Column(db.String(128))
    status = db.Column(db.String(32), default='in_progress')
    label_code = db.Column(db.String(32))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    scale = db.Column(db.Float)
    notes = db.Column(db.Text)
    tags = db.Column(db.Text)
    total_cost = db.Column(db.Float)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    default_unit = db.Column(db.String(32), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    variations = db.relationship('ProductVariation', backref='product', cascade="all, delete-orphan")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    events = db.relationship('ProductEvent', backref='product', lazy=True)

class ProductVariation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    sku = db.Column(db.String(64), unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProductEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    event_type = db.Column(db.String(64))
    note = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class InventoryItem(db.Model):
    __tablename__ = 'inventory_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    quantity = db.Column(db.Float, default=0)
    unit = db.Column(db.String(32))
    type = db.Column(db.String(32), default="ingredient")
    cost_per_unit = db.Column(db.Float, default=0.0)
    intermediate = db.Column(db.Boolean, default=False)
    expiration_date = db.Column(db.Date, nullable=True)
    perishable = db.Column(db.Boolean, default=False)

class InventoryUnit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)
    type = db.Column(db.String(16))
    aliases = db.Column(db.Text)
    base_equivalent = db.Column(db.Float)
    density_required = db.Column(db.Boolean, default=False)

class ProductUnit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BatchTimer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'))
    label = db.Column(db.String(64))
    due_at = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)

    batch = db.relationship('Batch', backref='timers')