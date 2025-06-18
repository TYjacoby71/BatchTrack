
from datetime import datetime, date
from flask_login import current_user, UserMixin
from ..extensions import db

class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    subscription_tier = db.Column(db.String(32), default='free')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    users = db.relationship('User', backref='organization')
    
    @property
    def active_users_count(self):
        return len([u for u in self.users if u.is_active])
    
    @property
    def owner(self):
        """Get the organization owner (first created user)"""
        return User.query.filter_by(organization_id=self.id).order_by(User.created_at).first()
    
    def can_add_users(self):
        """Check if organization can add more users based on subscription"""
        if self.subscription_tier == 'free':
            return self.active_users_count < 1  # Solo only
        elif self.subscription_tier == 'team':
            return self.active_users_count < 10  # Up to 10 users
        else:
            return True  # Unlimited for enterprise

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(32), default='user')
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    subscription_class = db.Column(db.String(32), default='free')
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.username
    
    @property
    def is_organization_owner(self):
        """Check if user is the owner of their organization"""
        # For now, assume first user in org is owner
        # Later you can add an explicit owner field
        first_user = User.query.filter_by(organization_id=self.organization_id).order_by(User.created_at).first()
        return first_user and first_user.id == self.id

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    symbol = db.Column(db.String(16), nullable=False)
    type = db.Column(db.String(32), nullable=False)  # weight, volume, count, etc.
    base_unit = db.Column(db.String(64), nullable=True)  # For conversions
    conversion_factor = db.Column(db.Float, nullable=True)  # To base unit
    is_active = db.Column(db.Boolean, default=True)

class CustomUnitMapping(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ingredient_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    unit_name = db.Column(db.String(64), nullable=False)
    conversion_factor = db.Column(db.Float, nullable=False)
    base_unit = db.Column(db.String(64), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ingredient_item = db.relationship('InventoryItem', backref='custom_units')

class IngredientCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6c757d')  # Bootstrap secondary color
    is_active = db.Column(db.Boolean, default=True)

class ConversionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    amount = db.Column(db.Float, nullable=False)
    from_unit = db.Column(db.String(64), nullable=False)
    to_unit = db.Column(db.String(64), nullable=False)
    result = db.Column(db.Float, nullable=False)
    conversion_type = db.Column(db.String(32), default='unit_to_unit')
    ingredient_name = db.Column(db.String(128))
    
    user = db.relationship('User', backref='conversion_logs')

class RecipeIngredient(db.Model):
    __tablename__ = 'recipe_ingredient'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    notes = db.Column(db.Text)
    order_position = db.Column(db.Integer, default=0)
    
    inventory_item = db.relationship('InventoryItem', backref='recipe_usages')

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
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
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
    
    recipe = db.relationship('Recipe', backref='batches')
    product = db.relationship('Product', backref='batches')
    variant = db.relationship('ProductVariation', backref='batches')

class BatchIngredient(db.Model):
    __tablename__ = 'batch_ingredient'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    
    batch = db.relationship('Batch', backref='batch_ingredients')
    inventory_item = db.relationship('InventoryItem', backref='batch_usages')

class BatchContainer(db.Model):
    __tablename__ = 'batch_container'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    container_size = db.Column(db.String(32), nullable=False)
    container_quantity = db.Column(db.Integer, nullable=False)
    fill_quantity = db.Column(db.Float)
    fill_unit = db.Column(db.String(32))
    
    batch = db.relationship('Batch', backref='containers')

class ExtraBatchContainer(db.Model):
    __tablename__ = 'extra_batch_container'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    container_size = db.Column(db.String(32), nullable=False)
    container_quantity = db.Column(db.Integer, nullable=False)
    fill_quantity = db.Column(db.Float)
    fill_unit = db.Column(db.String(32))
    
    batch = db.relationship('Batch', backref='extra_containers')

class InventoryHistory(db.Model):
    __tablename__ = 'inventory_history'
    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(32), nullable=False)  # manual_addition, batch_usage, spoil, trash, tester, damaged, recount
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    remaining_quantity = db.Column(db.Float, nullable=True)  # For FIFO tracking
    unit_cost = db.Column(db.Float, nullable=True)
    fifo_reference_id = db.Column(db.Integer, db.ForeignKey('inventory_history.id'), nullable=True)
    fifo_code = db.Column(db.String(32), nullable=True)  # Base32 encoded unique identifier
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Expiration tracking fields
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    inventory_item = db.relationship('InventoryItem', backref='history')
    batch = db.relationship('Batch')
    user = db.relationship('User')

class BatchTimer(db.Model):
    __tablename__ = 'batch_timer'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), default='active')  # active, completed, cancelled
    
    batch = db.relationship('Batch', backref='timers')

class ExtraBatchIngredient(db.Model):
    __tablename__ = 'extra_batch_ingredient'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    
    batch = db.relationship('Batch', backref='extra_ingredients')
    inventory_item = db.relationship('InventoryItem', backref='extra_batch_usages')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    product_base_unit = db.Column(db.String(32), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    low_stock_threshold = db.Column(db.Float, default=0)
    variations = db.relationship('ProductVariation', backref='product', cascade="all, delete-orphan")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    events = db.relationship('ProductEvent', backref='product', lazy=True)
    inventory = db.relationship('ProductInventory', backref='product', lazy=True)
    
    @property
    def total_inventory(self):
        """Total inventory across all variants"""
        return sum(inv.quantity for inv in self.inventory if inv.quantity > 0)
    
    @property
    def base_variant(self):
        """Get the Base ProductVariation for this product"""
        return next((v for v in self.variations if v.name == 'Base'), None)
    
    @property
    def variant_count(self):
        """Total number of variants including Base"""
        return len(self.variations)

class ProductInventory(db.Model):
    """FIFO-managed inventory for product outputs"""
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variation.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    unit = db.Column(db.String(32), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    # Expiration tracking fields
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)
    
    variant = db.relationship('ProductVariation', backref='inventory')
    batch = db.relationship('Batch')

class ProductVariation(db.Model):
    """Product variations (SKUs) - handles packaging, sizes, etc."""
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)  # 'Base', '2oz', '4oz', 'Trial Size', etc.
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('product_id', 'name', name='unique_product_variation'),)

class ProductEvent(db.Model):
    """Track major product lifecycle events"""
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    event_type = db.Column(db.String(32), nullable=False)  # created, variant_added, discontinued, etc.
    description = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    user = db.relationship('User')

class InventoryItem(db.Model):
    """Ingredients and raw materials"""
    __tablename__ = 'inventory_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('ingredient_category.id'))
    current_stock = db.Column(db.Float, default=0.0)
    stock_unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float, default=0.0)
    low_stock_threshold = db.Column(db.Float, default=0.0)
    density = db.Column(db.Float, nullable=True)  # g/ml for volume-weight conversions
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    category = db.relationship('IngredientCategory', backref='inventory_items')

class BatchInventoryLog(db.Model):
    """Log batch impacts on inventory for debugging"""
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    action = db.Column(db.String(32), nullable=False)  # deduct, credit
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    old_stock = db.Column(db.Float, nullable=False)
    new_stock = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    batch = db.relationship('Batch')
    inventory_item = db.relationship('InventoryItem')

class Tag(db.Model):
    """Tags for categorizing batches, products, etc."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    color = db.Column(db.String(7), default='#6c757d')  # hex color
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

class ProductInventoryHistory(db.Model):
    """FIFO tracking for product inventory similar to InventoryHistory"""
    id = db.Column(db.Integer, primary_key=True)
    product_inventory_id = db.Column(db.Integer, db.ForeignKey('product_inventory.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(32), nullable=False)  # manual_addition, batch_production, sold, spoil, trash, tester, damaged, recount
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    remaining_quantity = db.Column(db.Float, nullable=True)  # For FIFO tracking
    unit_cost = db.Column(db.Float, nullable=True)
    fifo_reference_id = db.Column(db.Integer, db.ForeignKey('product_inventory_history.id'), nullable=True)
    fifo_code = db.Column(db.String(32), nullable=True)  # Base32 encoded unique identifier
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Expiration tracking fields
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    product_inventory = db.relationship('ProductInventory', backref='history')
    batch = db.relationship('Batch')
    user = db.relationship('User')
