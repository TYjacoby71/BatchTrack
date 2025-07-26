from datetime import datetime, date
from flask_login import current_user, UserMixin
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

# Import forwarding for moved models
from .inventory import InventoryItem, InventoryHistory, BatchInventoryLog
from .recipe import Recipe, RecipeIngredient
from .batch import Batch, BatchIngredient, BatchContainer, ExtraBatchContainer, BatchTimer, ExtraBatchIngredient
from .unit import Unit, CustomUnitMapping, ConversionLog
from .category import IngredientCategory, Tag

# Make sure Organization and User are available for import
__all__ = ['Organization', 'User', 'InventoryItem', 'InventoryHistory', 'BatchInventoryLog', 
           'Recipe', 'RecipeIngredient', 'Batch', 'BatchIngredient', 'BatchContainer', 
           'ExtraBatchContainer', 'BatchTimer', 'ExtraBatchIngredient', 'Unit', 
           'CustomUnitMapping', 'ConversionLog', 'IngredientCategory', 'Tag']

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

    # Keep old string field for migration compatibility only (DO NOT USE)
    subscription_tier = db.Column(db.String(32), default='free')  # DEPRECATED - use tier relationship

    # Relationships
    users = db.relationship('User', backref='organization')
    tier = db.relationship('SubscriptionTier', foreign_keys=[subscription_tier_id])

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
        """Get the effective subscription tier from SubscriptionTier model"""
        if self.subscription_tier_id:
            from .subscription_tier import SubscriptionTier
            tier = SubscriptionTier.query.get(self.subscription_tier_id)
            return tier.key if tier else 'free'
        return 'free'

    @property
    def subscription_tier_obj(self):
        """Get the full SubscriptionTier object"""
        if self.subscription_tier_id:
            from .subscription_tier import SubscriptionTier
            return SubscriptionTier.query.get(self.subscription_tier_id)
        return None

    def get_subscription_features(self):
        """Get list of features for current subscription tier"""
        if not self.tier:
            return []

        # Load tier configuration
        from ..blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()

        if self.tier.key in tiers_config:
            return tiers_config[self.tier.key].get('fallback_features', [])

        return []

    def get_tier_display_name(self):
        """Get the display name for the current subscription tier"""
        if not self.tier:
            return 'Free'

        return self.tier.name

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
    password_hash = db.Column(db.String(255), nullable=False)
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

        # All users (including organization owners) check their assigned roles ONLY
        # The is_organization_owner flag is just a trigger to assign the role,
        # but permissions come from the role, not the flag
        roles = self.get_active_roles()
        for role in roles:
            if role.has_permission(permission_name):
                # Also check if the permission is available for the organization's tier
                from .permission import Permission
                permission = Permission.query.filter_by(name=permission_name).first()
                if permission and permission.is_available_for_tier(self.organization.effective_subscription_tier):
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