from datetime import datetime, date
from flask_login import current_user, UserMixin
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    contact_email = db.Column(db.String(256))
    subscription_tier = db.Column(db.String(32), default='free')  # free, trial, solo, team, enterprise
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    is_active = db.Column(db.Boolean, default=True)

    # Basic signup tracking (keep these for analytics)
    signup_source = db.Column(db.String(64), nullable=True)  # homepage_trial, webinar, etc.
    promo_code = db.Column(db.String(32), nullable=True)
    referral_code = db.Column(db.String(32), nullable=True)

    # Move billing to separate Subscription model for flexibility

    users = db.relationship('User', backref='organization')

    @property
    def active_users_count(self):
        # Only count users that belong to this organization AND are not developers
        return len([u for u in self.users if u.is_active and u.user_type != 'developer' and u.organization_id == self.id])

    @property
    def owner(self):
        """Get the organization owner (first created user)"""
        return User.query.filter_by(organization_id=self.id).order_by(User.created_at).first()

    def can_add_users(self):
        """Check if organization can add more active users based on subscription (excluding developers)"""
        active_non_dev_users = len([u for u in self.users if u.is_active and u.user_type != 'developer'])
        effective_tier = self.effective_subscription_tier
        if effective_tier == 'solo':
            return active_non_dev_users < 1  # Solo only
        elif effective_tier == 'team':
            return active_non_dev_users < 10  # Up to 10 active users
        elif effective_tier in ['enterprise', 'exempt']:
            return True  # Unlimited active users for enterprise/exempt
        else:
            return active_non_dev_users < 1  # Default to solo limits

    def get_max_users(self):
        """Get maximum users allowed for subscription tier"""
        tier_limits = {
            'solo': 1,
            'team': 10,
            'enterprise': float('inf'),
            'exempt': float('inf')
        }
        effective_tier = self.effective_subscription_tier
        return tier_limits.get(effective_tier, 1)

    @property
    def effective_subscription_tier(self):
        """Get the effective subscription tier (from subscription or fallback to organization tier)"""
        # Try to get from subscription model first
        try:
            from .subscription import Subscription
            subscription = Subscription.query.filter_by(organization_id=self.id).first()
            if subscription and subscription.status == 'active':
                return subscription.tier
        except (ImportError, AttributeError):
            pass

        # Fallback to organization subscription_tier
        return self.subscription_tier or 'free'

    def get_subscription_features(self):
        """Get features available for subscription tier"""
        features = {
            'solo': ['basic_production', 'inventory_tracking', 'recipe_management'],
            'team': ['basic_production', 'inventory_tracking', 'recipe_management', 'user_management', 'advanced_alerts', 'batch_tracking'],
            'enterprise': ['all_features', 'api_access', 'custom_integrations', 'priority_support'],
            'exempt': ['all_features', 'api_access', 'custom_integrations', 'priority_support', 'exempt_access']
        }
        effective_tier = self.effective_subscription_tier
        return features.get(effective_tier, features['solo'])

    def get_pricing_data(self):
        """Get dynamic pricing data from Stripe"""
        try:
            from ..services.pricing_service import PricingService
            return PricingService.get_pricing_data()
        except ImportError:
            return None

    def is_owner(self, user):
        """Check if user is owner of this organization"""
        return user.id == self.owner_id

    def owner_has_permission(self, user, permission_name):
        """Check if owner has permission through subscription tier (no bypass)"""
        if not self.is_owner(user):
            return False

        # Owners must still respect subscription tier limits
        from ..utils.permissions import _has_tier_permission
        return _has_tier_permission(self, permission_name)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    user_type = db.Column(db.String(32), default='customer')  # 'developer', 'customer'
    _is_organization_owner = db.Column('is_organization_owner', db.Boolean, nullable=True, default=False)  # Flag for organization owners (only for customer users)
    
    @property
    def is_organization_owner(self):
        """Unified organization owner check"""
        return (self.user_type == 'customer' and 
                self._is_organization_owner is True)
    
    @is_organization_owner.setter
    def is_organization_owner(self, value):
        self._is_organization_owner = value
        # Auto-assign role when flag is set to True
        if value is True and self.user_type == 'customer' and self.id:
            self.ensure_organization_owner_role()
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    last_login = db.Column(db.DateTime, nullable=True)
    timezone = db.Column(db.String(64), default='UTC')
    # role_id removed - using UserRoleAssignment table instead

    # Soft delete fields
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)

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

    def is_org_owner(self):
        """Check if user has organization owner role"""
        roles = self.get_active_roles()
        return any(role.name == 'organization_owner' for role in roles)
    
    def ensure_organization_owner_role(self):
        """Ensure organization owner has the proper role assigned"""
        # Only apply to customer users with the flag set
        if (self.user_type == 'customer' and 
            self.is_organization_owner is True):
            from .role import Role
            org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
            if org_owner_role:
                # Check if already assigned
                existing_assignment = False
                for assignment in self.role_assignments:
                    if assignment.is_active and assignment.role_id == org_owner_role.id:
                        existing_assignment = True
                        break
                
                if not existing_assignment:
                    self.assign_role(org_owner_role)
                    db.session.commit()
                    return True
        return False

    def get_active_roles(self):
        """Get all active roles for this user"""
        try:
            from .user_role_assignment import UserRoleAssignment
            from .role import Role
            from .developer_role import DeveloperRole

            assignments = UserRoleAssignment.query.filter_by(
                user_id=self.id,
                is_active=True
            ).all()

            roles = []
            for assignment in assignments:
                if assignment.role_id:
                    # Organization role
                    role = Role.query.get(assignment.role_id)
                    if role and role.is_active:
                        roles.append(role)
                elif assignment.developer_role_id:
                    # Developer role
                    dev_role = DeveloperRole.query.get(assignment.developer_role_id)
                    if dev_role and dev_role.is_active:
                        roles.append(dev_role)

            return roles
        except Exception as e:
            print(f"Error getting active roles for user {self.id}: {e}")
            return []

    def has_permission(self, permission_name):
        """Check if user has a specific permission through any of their roles"""
        # Developers check their developer roles
        if self.user_type == 'developer':
            return self.has_developer_permission(permission_name)

        # All users (including organization owners) check their assigned roles
        roles = self.get_active_roles()
        for role in roles:
            if role.has_permission(permission_name):
                # Also check if the permission is available for the organization's tier
                from .permission import Permission
                permission = Permission.query.filter_by(name=permission_name).first()
                if permission and permission.is_available_for_tier(self.organization.subscription_tier):
                    return True

        return False

    def has_developer_permission(self, permission_name):
        """Check if developer user has a specific developer permission"""
        if self.user_type != 'developer':
            return False

        # Get developer role assignments for this user
        from .user_role_assignment import UserRoleAssignment

        # Check if user has any developer roles assigned
        assignments = UserRoleAssignment.query.filter_by(
            user_id=self.id,
            is_active=True
        ).filter(UserRoleAssignment.developer_role_id.isnot(None)).all()

        for assignment in assignments:
            if assignment.developer_role and assignment.developer_role.has_permission(permission_name):
                return True

        return False

    def assign_role(self, role, assigned_by=None):
        """Assign a role to this user"""
        from .user_role_assignment import UserRoleAssignment

        # Check if already assigned
        existing = UserRoleAssignment.query.filter_by(
            user_id=self.id,
            role_id=role.id,
            organization_id=self.organization_id
        ).first()

        if existing:
            existing.is_active = True
            existing.assigned_by = assigned_by.id if assigned_by else None
            existing.assigned_at = TimezoneUtils.utc_now()
        else:
            assignment = UserRoleAssignment(
                user_id=self.id,
                role_id=role.id,
                organization_id=self.organization_id,
                assigned_by=assigned_by.id if assigned_by else None
            )
            db.session.add(assignment)

        db.session.commit()

    def remove_role(self, role):
        """Remove a role from this user"""
        from .user_role_assignment import UserRoleAssignment

        assignment = UserRoleAssignment.query.filter_by(
            user_id=self.id,
            role_id=role.id,
            organization_id=self.organization_id
        ).first()

        if assignment:
            assignment.is_active = False
            db.session.commit()

    def soft_delete(self, deleted_by_user=None):
        """Soft delete this user - preserves data but removes access"""
        self.is_deleted = True
        self.is_active = False  # Also deactivate
        self.deleted_at = TimezoneUtils.utc_now()
        if deleted_by_user:
            self.deleted_by = deleted_by_user.id

        # Deactivate all role assignments
        from .user_role_assignment import UserRoleAssignment
        assignments = UserRoleAssignment.query.filter_by(user_id=self.id).all()
        for assignment in assignments:
            assignment.is_active = False

        db.session.commit()

    def restore(self, restored_by_user=None):
        """Restore a soft-deleted user"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        # Note: is_active and role assignments need to be manually restored
        db.session.commit()

    @property
    def is_soft_deleted(self):
        """Check if user is soft deleted"""
        return self.is_deleted is True

    @property
    def display_role(self):
        """Get display-friendly role description"""
        if self.user_type == 'developer':
            return 'System Developer'
        elif self.is_organization_owner and self.organization:
            tier = self.organization.subscription_tier.title()
            return f'{tier} Owner'
        else:
            roles = self.get_active_roles()
            if roles:
                role_names = [role.name for role in roles]
                return f'Team Member ({", ".join(role_names)})'
            return 'Team Member (No Roles)'

    def __repr__(self):
        return f'<User {self.username}>'

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
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

    # Add unique constraints
    __table_args__ = (
        # Standard units (is_custom=False) must have unique names globally
        db.Index('ix_unit_standard_unique', 'name', unique=True),
        # Custom units must have unique names within organization  
        db.UniqueConstraint('name', 'name', 'organization_id', name='_unit_name_org_uc'),
    )

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
    conversion_factor = db.Column(db.Float, nullable=False)
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

    def belongs_to_user(self):
        """Check if this record belongs to the current user's organization"""
        if not current_user.is_authenticated:
            return False
        return self.organization_id == current_user.organization_id

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
    name = db.Column(db.String(64), nullable=False)
    color = db.Column(db.String(7), default='#6c757d')  # hex color
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Add unique constraint per organization
    __table_args__ = (
        db.UniqueConstraint('name', 'organization_id', name='_tag_name_org_uc'),
    )