# app/models/models.py
# Canonical re-exports for tests/legacy imports. Safe, no-crash imports.
import importlib
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import event
from datetime import datetime
import re
import secrets

def _export(targets):
    g = globals()
    for module, name, alias in targets:
        try:
            mod = importlib.import_module(f"{__package__}.{module}")
            cls = getattr(mod, name)
            g[alias or name] = cls
        except Exception:
            # silently skip if module/class doesn't exist
            pass

_export([
    # Inventory / FIFO
    ("inventory", "InventoryItem", None),
    ("unified_inventory_history", "UnifiedInventoryHistory", "FIFOLot"),     # alias UnifiedInventoryHistory as FIFOLot
    ("inventory", "InventoryHistory", None),  # Legacy - kept for backward compatibility
    ("inventory", "BatchInventoryLog", None),

    # Create Ingredient alias to InventoryItem (common pattern)
    ("inventory", "InventoryItem", "Ingredient"),

    # Products
    ("product", "Product", None),
    ("product", "ProductSKU", None),

    # Auth/Org/ACL - these are defined in this file below
    ("subscription_tier", "SubscriptionTier", None),
    ("addon", "Addon", None),
    ("permission", "Permission", None),
    ("role", "Role", None),

    # Recipes and Batches
    ("batch", "Batch", None),
    ("batch", "BatchIngredient", None),
    ("batch", "BatchContainer", None),
    ("batch", "ExtraBatchContainer", None),
    ("batch", "BatchTimer", None),
    ("batch", "ExtraBatchIngredient", None),

    # Units and Categories
    ("unit", "Unit", None),
    ("unit", "CustomUnitMapping", None),
    ("unit", "ConversionLog", None),
    ("category", "IngredientCategory", None),
    ("category", "InventoryCategory", None),
    ("category", "Tag", None),
    ("product_category", "ProductCategory", None),
    ("global_item", "GlobalItem", None),
    ("batchbot_usage", "BatchBotUsage", None),
    ("batchbot_credit", "BatchBotCreditBundle", None),
    ("recipe_marketplace", "RecipeModerationEvent", None),
])

# Build __all__ from whatever successfully imported
__all__ = [k for k, v in globals().items() if k[0].isupper() and hasattr(v, "__mro__")]

# Keep the core models that are defined in this file
from datetime import datetime, date
from flask_login import current_user, UserMixin
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    contact_email = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    is_active = db.Column(db.Boolean, default=True)

    # Basic signup tracking (keep these for analytics)
    signup_source = db.Column(db.String(64), nullable=True)  # homepage_trial, webinar, etc.
    promo_code = db.Column(db.String(32), nullable=True)
    referral_code = db.Column(db.String(32), nullable=True)

    # Move billing to separate Subscription model for flexibility

    # Subscription tier (relationship to SubscriptionTier) - SINGLE SOURCE OF TRUTH
    subscription_tier_id = db.Column(db.Integer, db.ForeignKey('subscription_tier.id'), nullable=True)

    # Whop integration fields (replacing Stripe)
    whop_license_key = db.Column(db.String(128), nullable=True)
    whop_product_tier = db.Column(db.String(32), nullable=True)
    whop_verified = db.Column(db.Boolean, default=False)

    # Legacy Stripe fields (keep for migration compatibility)
    stripe_subscription_id = db.Column(db.String(128), nullable=True)  # DEPRECATED
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    billing_info = db.Column(db.Text, nullable=True)  # JSON field for billing details
    next_billing_date = db.Column(db.Date, nullable=True)
    subscription_status = db.Column(db.String(32), default='inactive')  # active, past_due, canceled, etc.

    # Billing fields
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    whop_license_key = db.Column(db.String(255), nullable=True)
    billing_status = db.Column(db.String(50), default='active', nullable=False)  # active, suspended, cancelled

    # Offline support (removed)

    # Inventory costing policy
    inventory_cost_method = db.Column(db.String(16), nullable=True)  # 'fifo' | 'average' (default handled in logic)
    inventory_cost_method_changed_at = db.Column(db.DateTime, nullable=True)

    # Recipe marketplace governance
    recipe_sales_blocked = db.Column(db.Boolean, default=False)
    recipe_library_blocked = db.Column(db.Boolean, default=False)
    recipe_violation_count = db.Column(db.Integer, default=0)
    recipe_policy_notes = db.Column(db.Text, nullable=True)

    # Relationships
    users = db.relationship('User', backref='organization')
    subscription_tier = db.relationship('SubscriptionTier', foreign_keys=[subscription_tier_id])
    tier = db.relationship('SubscriptionTier', foreign_keys=[subscription_tier_id], overlaps="subscription_tier")  # Alias for backward compatibility

    @property
    def active_users_count(self):
        # Only count users that belong to this organization AND are not developers
        return len([u for u in self.users if u.is_active and u.user_type != 'developer'])

    @property
    def owner(self):
        """Get the organization owner (first created user)"""
        return User.query.filter_by(organization_id=self.id).order_by(User.created_at).first()

    def can_add_users(self):
        """Check if organization can add more active users based on subscription (excluding developers)"""
        active_non_dev_users = len([u for u in self.users if u.is_active and u.user_type != 'developer'])

        if not self.tier:
            return active_non_dev_users < 1  # Default to 1 user limit

        # Use tier's user_limit (-1 means unlimited)
        if self.tier.user_limit == -1:
            return True  # Unlimited

        return active_non_dev_users < self.tier.user_limit

    def get_max_users(self):
        """Get maximum users allowed for subscription tier"""
        if not self.tier:
            return 1  # Default

        if self.tier.user_limit == -1:
            return float('inf')  # Unlimited

        return self.tier.user_limit

    @property
    def effective_subscription_tier(self):
        """Get the effective subscription tier identifier (string id or 'exempt')."""
        if not self.tier:
            return 'exempt'
        return str(self.tier.id)

    @property
    def subscription_tier_obj(self):
        """Get the full SubscriptionTier object (alias for .tier)"""
        return self.tier

    def get_subscription_features(self):
        """Get list of features for this organization's subscription tier"""
        if not self.tier:
            return []

        # Get features from tier's permissions and addons
        features = []

        # Add permission-based features
        if self.tier.permissions:
            for permission in self.tier.permissions:
                features.append(permission.name)

        # Add addon-based features
        if self.tier.allowed_addons:
            for addon in self.tier.allowed_addons:
                if addon.is_active:
                    features.append(addon.function_key if hasattr(addon, 'function_key') else addon.name)

        return features

    def get_tier_display_name(self):
        """Get the display name for the current subscription tier"""
        if not self.tier:
            return 'Free'

        return self.tier.name

    def get_pricing_data(self):
        """Get pricing data from local config - simple and always available"""
        try:
            from ..services.billing_service import BillingService
            return BillingService.get_comprehensive_pricing_data()
        except Exception:
            return {'tiers': {}, 'available': False}

    def is_owner(self, user):
        """Check if user is owner of this organization"""
        owner = self.owner
        return owner and user.id == owner.id

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
    password_hash = db.Column(db.String(255), nullable=True, default='', server_default='')
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)  # NULL for developers
    user_type = db.Column(db.String(32), default='customer')  # 'developer', 'customer'
    _is_organization_owner = db.Column('is_organization_owner', db.Boolean, nullable=True, default=False)  # Flag for organization owners (only for customer users)

    @property
    def is_organization_owner(self):
        """Check if user has organization owner role - AUTHORITATIVE"""
        if self.user_type != 'customer':
            return False

        # Check active roles for organization_owner role
        roles = self.get_active_roles()
        return any(role.name == 'organization_owner' for role in roles)

    @is_organization_owner.setter
    def is_organization_owner(self, value):
        """Sync the flag for legacy compatibility and assign/remove role"""
        self._is_organization_owner = value

        if value is True and self.user_type == 'customer' and self.id:
            # Ensure role is assigned
            self.ensure_organization_owner_role()
        elif value is False and self.id:
            # Remove the role
            from .role import Role
            org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
            if org_owner_role:
                self.remove_role(org_owner_role)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    last_login = db.Column(db.DateTime, nullable=True)
    active_session_token = db.Column(db.String(255), nullable=True)
    # role_id removed - using UserRoleAssignment table instead

    # Email verification fields
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(255), nullable=True)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)

    # OAuth fields
    oauth_provider = db.Column(db.String(50), nullable=True)  # 'google', etc.
    oauth_provider_id = db.Column(db.String(255), nullable=True)

    # Password reset fields
    password_reset_token = db.Column(db.String(255), nullable=True)
    password_reset_sent_at = db.Column(db.DateTime, nullable=True)

    # Soft delete fields
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)

    # Indexes
    __table_args__ = (
        db.Index('ix_user_org', 'organization_id'),
        db.Index('ix_user_org_created_at', 'organization_id', 'created_at'),
        db.Index('ix_user_active_type', 'is_active', 'user_type'),
    )

    # Legacy compatibility: is_verified hybrid property
    @hybrid_property
    def is_verified(self):
        """Legacy compatibility: maps to email_verified boolean"""
        return self.email_verified

    @is_verified.setter
    def is_verified(self, value: bool):
        """Legacy compatibility: sets email_verified boolean"""
        self.email_verified = value

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
    def timezone(self):
        """Get user's timezone from preferences, default to UTC"""
        from .user_preferences import UserPreferences
        preferences = UserPreferences.query.filter_by(user_id=self.id).first()
        if preferences:
            return preferences.timezone or 'UTC'
        return 'UTC'

    @timezone.setter
    def timezone(self, value):
        """Set user's timezone in preferences"""
        from .user_preferences import UserPreferences
        preferences = UserPreferences.query.filter_by(user_id=self.id).first()
        
        if not preferences:
            # Create preferences if they don't exist and user has organization
            if self.organization_id:
                preferences = UserPreferences(
                    user_id=self.id,
                    organization_id=self.organization_id,
                    timezone=value or 'UTC'
                )
                db.session.add(preferences)
        else:
            preferences.timezone = value or 'UTC'

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
            from ..extensions import db

            # Force rollback before attempting query
            db.session.rollback()

            assignments = UserRoleAssignment.query.filter_by(
                user_id=self.id,
                is_active=True
            ).all()

            roles = []
            for assignment in assignments:
                if assignment.role_id:
                    # Organization role
                    role = db.session.get(Role, assignment.role_id)
                    if role and role.is_active:
                        roles.append(role)
                elif assignment.developer_role_id:
                    # Developer role
                    dev_role = db.session.get(DeveloperRole, assignment.developer_role_id)
                    if dev_role and dev_role.is_active:
                        roles.append(dev_role)

            return roles
        except Exception as e:
            print("---!!! USER ROLE ASSIGNMENT ERROR (POTENTIAL ORIGINAL SIN?) !!!---")
            print(f"Error getting active roles for user {self.id}: {e}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error details: {str(e)}")
            print("------------------------------------------------------------------")

            # Try to rollback and clean up
            try:
                from ..extensions import db
                db.session.rollback()
            except:
                pass

            return []

    def has_permission(self, permission_name):
        """Check if user has a specific permission through any of their roles"""
        # Handle enum permission names by converting to string
        if hasattr(permission_name, 'value'):
            permission_name = permission_name.value

        # Developers check their developer roles
        if self.user_type == 'developer':
            return self.has_developer_permission(permission_name)

        # Get roles from both active assignments and direct role relationships (for tests)
        roles = self.get_active_roles()

        # Also check direct role relationships (backwards compatibility for tests)
        if hasattr(self, 'roles'):
            for role in self.roles:
                if role not in roles:
                    roles.append(role)

        for role in roles:
            if role.has_permission(permission_name):
                # Also check if the permission is available for the organization's tier
                if self.organization and self.organization.tier:
                    # Check if the tier allows this permission
                    if self.organization.tier.has_permission(permission_name):
                        return True
                else:
                    # No tier restriction - allow if role has permission
                    return True

        return False

    def has_any_permission(self, permissions):
        """Check if user has any of the specified permissions"""
        for permission_name in permissions:
            if self.has_permission(permission_name):
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
        from .developer_role import DeveloperRole

        # Determine if this is a developer role or organization role
        is_developer_role = isinstance(role, DeveloperRole)

        if is_developer_role:
            # Developer role assignment - no organization context
            existing = UserRoleAssignment.query.filter_by(
                user_id=self.id,
                developer_role_id=role.id,
                organization_id=None  # Developer roles never have organization_id
            ).first()

            if existing:
                existing.is_active = True
                existing.assigned_by = assigned_by.id if assigned_by else None
                existing.assigned_at = TimezoneUtils.utc_now()
            else:
                assignment = UserRoleAssignment(
                    user_id=self.id,
                    developer_role_id=role.id,
                    role_id=None,  # No organization role
                    organization_id=None,  # CRITICAL: No organization for developer roles
                    assigned_by=assigned_by.id if assigned_by else None
                )
                db.session.add(assignment)
        else:
            # Organization role assignment - requires organization context
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
                    developer_role_id=None,  # No developer role
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

    def restore(self, restored_by_user=None, restore_roles=True, make_active=True):
        """Restore a soft-deleted user with optional role and active status restoration"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None

        if make_active:
            self.is_active = True

        if restore_roles:
            # Reactivate all role assignments that were deactivated during soft delete
            from .user_role_assignment import UserRoleAssignment
            assignments = UserRoleAssignment.query.filter_by(user_id=self.id).all()
            for assignment in assignments:
                assignment.is_active = True

        db.session.commit()

    @property
    def is_soft_deleted(self):
        """Check if user is soft deleted"""
        return self.is_deleted is True

    @property
    def is_developer(self):
        """Check if user is a developer"""
        return self.user_type == 'developer'

    @property
    def display_role(self):
        """Get display-friendly role description"""
        if self.user_type == 'developer':
            return 'System Developer'
        elif self.is_organization_owner and self.organization:
            tier_name = self.organization.tier.name if self.organization.tier else 'Exempt'
            return f'{tier_name} Owner'
        else:
            roles = self.get_active_roles()
            if roles:
                role_names = [role.name for role in roles]
                return f'Team Member ({", ".join(role_names)})'
            return 'Team Member (No Roles)'

    def __repr__(self):
        return f'<User {self.username}>'

@event.listens_for(User, "before_insert")
def _default_username_before_insert(mapper, connection, target):
    """Auto-generate username if not provided (for test compatibility)"""
    if not getattr(target, "username", None):
        base = None
        if getattr(target, "email", None):
            local = target.email.split("@", 1)[0]
            base = re.sub(r"[^a-zA-Z0-9_.-]", "", local) or None
        target.username = (base or "user") + "_" + secrets.token_hex(3)

# Add the imported classes to __all__
__all__.extend(['Organization', 'User'])