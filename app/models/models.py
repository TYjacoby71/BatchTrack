from datetime import datetime, date
from flask_login import current_user, UserMixin
from ..extensions import db
from .mixins import ScopedModelMixin
from . import TimezoneUtils

class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    subscription_tier = db.Column(db.String(32), default='free')
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
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
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    subscription_class = db.Column(db.String(32), default='free')
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    is_owner = db.Column(db.Boolean, default=False)  # Explicit owner flag
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationship to role
    user_role = db.relationship('Role', backref='assigned_users')

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
        return self.is_owner

    def has_permission(self, permission_name):
        """Check if user has a specific permission"""
        if not self.user_role:
            return False
        return self.user_role.has_permission(permission_name)

    def __repr__(self):
        return f'<User {self.username}>'

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    symbol = db.Column(db.String(16), nullable=False)
    type = db.Column(db.String(32), nullable=False)  # weight, volume, count, etc.
    base_unit = db.Column(db.String(64), nullable=True)  # For conversions
    conversion_factor = db.Column(db.Float, nullable=True)  # To base unit
    is_active = db.Column(db.Boolean, default=True)
    is_custom = db.Column(db.Boolean, default=False)
    is_mapped = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)  # Only for custom units
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    @classmethod
    def scoped(cls):
        """Return query filtered by current user's organization for custom units only"""
        if not current_user.is_authenticated:
            return cls.query.filter(False)  # Return empty query if no user
        # Return all standard units + user's custom units
        return cls.query.filter(
            (cls.is_custom == False) | 
            (cls.organization_id == current_user.organization_id)
        )

    def belongs_to_user(self):
        """Check if this record belongs to the current user's organization (for custom units only)"""
        if not self.is_custom:
            return True  # Standard units belong to everyone
        if not current_user.is_authenticated:
            return False
        return self.organization_id == current_user.organization_id

class CustomUnitMapping(ScopedModelMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_unit = db.Column(db.String(64), nullable=False)
    to_unit = db.Column(db.String(64), nullable=False)
    multiplier = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

class IngredientCategory(ScopedModelMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6c757d')  # Bootstrap secondary color
    default_density = db.Column(db.Float, nullable=True)  # Default density for category in g/ml
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

class ConversionLog(ScopedModelMixin, db.Model):
    __tablename__ = 'conversion_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    amount = db.Column(db.Float, nullable=False)
    from_unit = db.Column(db.String(32), nullable=False)
    to_unit = db.Column(db.String(32), nullable=False)
    result = db.Column(db.Float, nullable=False)
    conversion_type = db.Column(db.String(64), nullable=False)
    ingredient_name = db.Column(db.String(128), nullable=True)

    user = db.relationship('User', backref='conversion_logs')

class RecipeIngredient(ScopedModelMixin, db.Model):
    __tablename__ = 'recipe_ingredient'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    notes = db.Column(db.Text)
    order_position = db.Column(db.Integer, default=0)

    inventory_item = db.relationship('InventoryItem', backref='recipe_usages')

class Recipe(ScopedModelMixin, db.Model):
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
    allowed_containers = db.Column(db.PickleType, default=list)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    parent = db.relationship('Recipe', remote_side=[id], backref='variations')
    recipe_ingredients = db.relationship('RecipeIngredient', backref='recipe', cascade="all, delete-orphan")

class Batch(ScopedModelMixin, db.Model):
    __tablename__ = 'batch'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    label_code = db.Column(db.String(32), unique=True)
    batch_type = db.Column(db.String(32), nullable=False)  # 'ingredient' or 'product'
    projected_yield = db.Column(db.Float)
    projected_yield_unit = db.Column(db.String(50))
    # Product assignment for finish batch
    sku_id = db.Column(db.Integer, db.ForeignKey('product_sku.inventory_item_id'), nullable=True)
    final_quantity = db.Column(db.Float)
    output_unit = db.Column(db.String(50))
    scale = db.Column(db.Float, default=1.0)
    status = db.Column(db.String(50), default='in_progress')  # in_progress, completed, failed, cancelled
    status_reason = db.Column(db.Text)  # Optional reason for status change
    notes = db.Column(db.Text)
    tags = db.Column(db.Text)
    total_cost = db.Column(db.Float)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    started_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    completed_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    inventory_credited = db.Column(db.Boolean, default=False)  # Track if inventory was returned
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer)
    expiration_date = db.Column(db.DateTime)
    remaining_quantity = db.Column(db.Float, nullable=True)

    recipe = db.relationship('Recipe', backref='batches')
    sku = db.relationship('ProductSKU', foreign_keys=[sku_id], backref='batches')

class BatchIngredient(ScopedModelMixin, db.Model):
    __tablename__ = 'batch_ingredient'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float)
    total_cost = db.Column(db.Float)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)

    batch = db.relationship('Batch', backref='batch_ingredients')
    inventory_item = db.relationship('InventoryItem', backref='batch_usages')

class BatchContainer(ScopedModelMixin, db.Model):
    __tablename__ = 'batch_container'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    container_quantity = db.Column(db.Integer, nullable=False)  # Number of containers used
    quantity_used = db.Column(db.Integer, nullable=False)  # Same as container_quantity for backwards compatibility
    fill_quantity = db.Column(db.Float)  # How much product each container holds
    fill_unit = db.Column(db.String(32))  # Unit for fill_quantity
    cost_each = db.Column(db.Float)  # Cost per container

    batch = db.relationship('Batch', backref='containers')
    container = db.relationship('InventoryItem')

class ExtraBatchContainer(ScopedModelMixin, db.Model):
    __tablename__ = 'extra_batch_container'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    container_quantity = db.Column(db.Integer, nullable=False)  # Number of containers used
    quantity_used = db.Column(db.Integer, nullable=False)  # Same as container_quantity for backwards compatibility
    fill_quantity = db.Column(db.Float)  # How much product each container holds
    fill_unit = db.Column(db.String(32))  # Unit for fill_quantity
    cost_each = db.Column(db.Float)  # Cost per container
    reason = db.Column(db.String(20), nullable=False, default='extra_yield')  # Track why container was added

    batch = db.relationship('Batch', backref='extra_containers')
    container = db.relationship('InventoryItem')

class InventoryHistory(ScopedModelMixin, db.Model):
    __tablename__ = 'inventory_history'
    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
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
    quantity_used = db.Column(db.Float, default=0.0)  # Track actual consumption vs deduction
    used_for_batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)  # Track which batch used this
    # Expiration tracking fields
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.DateTime, nullable=True)
    # Relationships
    inventory_item = db.relationship('InventoryItem', backref='history')
    batch = db.relationship('Batch', foreign_keys=[batch_id])
    used_for_batch = db.relationship('Batch', foreign_keys=[used_for_batch_id])
    user = db.relationship('User')

class BatchTimer(ScopedModelMixin, db.Model):
    __tablename__ = 'batch_timer'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), default='active')  # active, completed, cancelled
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    batch = db.relationship('Batch', backref='timers')

class ExtraBatchIngredient(ScopedModelMixin, db.Model):
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

class InventoryItem(ScopedModelMixin, db.Model):
    """Ingredients and raw materials"""
    __tablename__ = 'inventory_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('ingredient_category.id'))
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(32), nullable=False)
    cost_per_unit = db.Column(db.Float, default=0.0)
    low_stock_threshold = db.Column(db.Float, default=0.0)
    density = db.Column(db.Float, nullable=True)  # g/ml for volume-weight conversions
    type = db.Column(db.String(32), nullable=False, default='ingredient')  # 'ingredient', 'container', 'product', or 'product-reserved'
    is_active = db.Column(db.Boolean, default=True)
    is_archived = db.Column(db.Boolean, default=False)
    # Perishable tracking fields
    is_perishable = db.Column(db.Boolean, default=False)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    expiration_date = db.Column(db.Date, nullable=True)
    # Container-specific fields
    storage_amount = db.Column(db.Float, nullable=True)
    storage_unit = db.Column(db.String(32), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    # Density for unit conversion (g/mL)
    density = db.Column(db.Float, nullable=True)

    # Intermediate ingredient flag
    intermediate = db.Column(db.Boolean, default=False)

    # Organization relationship
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    organization = db.relationship('Organization', backref='inventory_items')

    category = db.relationship('IngredientCategory', backref='inventory_items')

    @property
    def available_quantity(self):
        """Get non-expired quantity available for use"""
        if not self.is_perishable:
            return self.quantity

        from datetime import datetime
        from sqlalchemy import and_

        today = datetime.now().date()
        expired_total = db.session.query(db.func.sum(InventoryHistory.remaining_quantity))\
            .filter(and_(
                InventoryHistory.inventory_item_id == self.id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date < today
            )).scalar() or 0

        return max(0, self.quantity - expired_total)

    @property 
    def expired_quantity(self):
        """Get expired quantity awaiting physical removal"""
        if not self.is_perishable:
            return 0

        from datetime import datetime
        from sqlalchemy import and_

        today = datetime.now().date()
        return db.session.query(db.func.sum(InventoryHistory.remaining_quantity))\
            .filter(and_(
                InventoryHistory.inventory_item_id == self.id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.expiration_date != None,
                InventoryHistory.expiration_date < today
            )).scalar() or 0

class BatchInventoryLog(ScopedModelMixin, db.Model):
    """Log batch impacts on inventory for debugging"""
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    action = db.Column(db.String(32), nullable=False)  # deduct, credit
    quantity_change = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    old_stock = db.Column(db.Float, nullable=False)
    new_stock = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    batch = db.relationship('Batch')
    inventory_item = db.relationship('InventoryItem')

class Tag(ScopedModelMixin, db.Model):
    """Tags for categorizing batches, products, etc."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    color = db.Column(db.String(7), default='#6c757d')  # hex color
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)