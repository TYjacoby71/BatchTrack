from datetime import datetime
from flask_login import current_user, UserMixin
from datetime import date
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(32), default='user')

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    type = db.Column(db.String(32), nullable=False)
    base_unit = db.Column(db.String(64), nullable=False)
    multiplier_to_base = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_custom = db.Column(db.Boolean, default=False)
    is_mapped = db.Column(db.Boolean, default=False)

class CustomUnitMapping(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    from_unit = db.Column(db.String(64), nullable=False)
    to_unit = db.Column(db.String(64), nullable=False)
    multiplier = db.Column(db.Float, nullable=False)

class IngredientCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    default_density = db.Column(db.Float, nullable=False)

class ConversionLog(db.Model):
    __tablename__ = 'conversion_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    amount = db.Column(db.Float, nullable=False)
    from_unit = db.Column(db.String(64), nullable=False)
    to_unit = db.Column(db.String(64), nullable=False)
    result = db.Column(db.Float, nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)
    density_used = db.Column(db.Float, nullable=True)
    ingredient = db.relationship('InventoryItem', backref='conversion_logs')

class RecipeIngredient(db.Model):
    __tablename__ = 'recipe_ingredients'
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id', ondelete='CASCADE'), primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id', ondelete='CASCADE'), primary_key=True)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    unit = db.Column(db.String(32), nullable=False, default='count')
    inventory_item = db.relationship('InventoryItem', backref=db.backref('recipe_ingredients', lazy='dynamic', cascade="all, delete-orphan"))

    def __init__(self, **kwargs):
        super(RecipeIngredient, self).__init__(**kwargs)
        if not self.unit:
            self.unit = 'count'
        if self.amount is None:
            self.amount = 0.0

class Recipe(db.Model):
    __tablename__ = 'recipe'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    instructions = db.Column(db.Text)
    label_prefix = db.Column(db.String(8))
    qr_image = db.Column(db.String(128))
    parent_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    is_locked = db.Column(db.Boolean, default=False)
    predicted_yield = db.Column(db.Float, default=0.0)
    predicted_yield_unit = db.Column(db.String(50), default="oz")
    requires_containers = db.Column(db.Boolean, default=False)
    allowed_containers = db.Column(db.PickleType, default=list)
    parent = db.relationship('Recipe', remote_side=[id], backref='variations')
    recipe_ingredients = db.relationship('RecipeIngredient', backref='recipe', cascade="all, delete-orphan")

class Batch(db.Model):
    __tablename__ = 'batch'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    label_code = db.Column(db.String(32), unique=True)
    batch_type = db.Column(db.String(32), nullable=False)  # 'ingredient' or 'product'
    projected_yield = db.Column(db.Float)
    projected_yield_unit = db.Column(db.String(50))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variation.id'))
    final_quantity = db.Column(db.Float)
    output_unit = db.Column(db.String(50))
    scale = db.Column(db.Float, default=1.0)
    status = db.Column(db.String(50), default='in_progress')  # in_progress, completed, failed, cancelled
    status_reason = db.Column(db.Text)  # Optional reason for status change
    notes = db.Column(db.Text)
    tags = db.Column(db.Text)
    total_cost = db.Column(db.Float)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    inventory_credited = db.Column(db.Boolean, default=False)  # Track if inventory was returned
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer)
    expiration_date = db.Column(db.DateTime)
    remaining_quantity = db.Column(db.Float, nullable=True)

    @property
    def status_display(self):
        """Human readable status with timestamp"""
        if self.status == 'in_progress':
            return f"In Progress (since {self.started_at.strftime('%Y-%m-%d %H:%M')})"
        elif self.status == 'completed':
            return f"Completed on {self.completed_at.strftime('%Y-%m-%d %H:%M')}"
        elif self.status == 'failed':
            return f"Failed on {self.failed_at.strftime('%Y-%m-%d %H:%M')}"
        elif self.status == 'cancelled':
            return f"Cancelled on {self.cancelled_at.strftime('%Y-%m-%d %H:%M')}"
        return self.status.title()

    recipe = db.relationship('Recipe', backref='batches')
    ingredients = db.relationship('BatchIngredient', backref='batch', cascade="all, delete-orphan")
    containers = db.relationship('BatchContainer', backref='batch', cascade="all, delete-orphan")
    extra_containers = db.relationship('ExtraBatchContainer', backref='batch', cascade="all, delete-orphan")
    timers = db.relationship('BatchTimer', backref='batch', cascade="all, delete-orphan")

class BatchIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    amount_used = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float, nullable=True)
    ingredient = db.relationship('InventoryItem', backref='batch_ingredients')

class BatchContainer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity_used = db.Column(db.Integer, nullable=False)
    cost_each = db.Column(db.Float)
    container = db.relationship('InventoryItem', backref='batch_containers')

class ExtraBatchContainer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)

class InventoryHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(32), nullable=False)  # batch, refunded, restock, spoil, trash, recount
    quantity_change = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float)  # Only for purchases
    source = db.Column(db.String(128))  # Vendor name or batch number
    is_perishable = db.Column(db.Boolean, default=False)
    expiration_date = db.Column(db.DateTime, nullable=True)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    used_for_batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'))
    note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    inventory_item = db.relationship('InventoryItem', backref='history')
    batch = db.relationship('Batch')
    user = db.relationship('User')

    quantity_used = db.Column(db.Integer, nullable=False)
    cost_each = db.Column(db.Float)
    container = db.relationship('InventoryItem', backref=db.backref('extra_batch_containers', overlaps="history,inventory_item"))

class BatchTimer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    name = db.Column(db.String(64), nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), nullable=True, default='pending')

class ExtraBatchIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float, nullable=True)

    batch = db.relationship('Batch', backref='extra_ingredients')
    ingredient = db.relationship('InventoryItem')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    default_unit = db.Column(db.String(32), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    low_stock_threshold = db.Column(db.Float, default=0)
    variations = db.relationship('ProductVariation', backref='product', cascade="all, delete-orphan")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    events = db.relationship('ProductEvent', backref='product', lazy=True)
    inventory = db.relationship('ProductInventory', backref='product', lazy=True)

class ProductInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    variant = db.Column(db.String(100))
    unit = db.Column(db.String(50))
    quantity = db.Column(db.Float)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'))
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    expiration_date = db.Column(db.Date, nullable=True)

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
    low_stock_threshold = db.Column(db.Float, default=0)
    is_perishable = db.Column(db.Boolean, default=False)
    storage_amount = db.Column(db.Float, default=0.0)  # How much this container holds
    storage_unit = db.Column(db.String(50), default="")  # e.g., oz, ml, count
    density = db.Column(db.Float, nullable=True)  # Per-item density override
    category_id = db.Column(db.Integer, db.ForeignKey('ingredient_category.id'), nullable=True)
    category = db.relationship('IngredientCategory', backref='ingredients')

class ProductUnit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)

class BatchInventoryLog(db.Model):
    """Tracks changes to batch inventory quantities"""
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    quantity_change = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(32), nullable=False)  # consumed, expired, lost, disposed
    notes = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    batch = db.relationship('Batch', backref='inventory_logs')

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)