from datetime import datetime
from ..extensions import db
from sqlalchemy.orm import backref

# Association table for subscription tier permissions
subscription_tier_permission = db.Table('subscription_tier_permission',
    db.Column('tier_id', db.Integer, db.ForeignKey('subscription_tier.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)

# Association table for which add-ons are allowed on a subscription tier
tier_allowed_addon = db.Table('tier_allowed_addon',
    db.Column('tier_id', db.Integer, db.ForeignKey('subscription_tier.id'), primary_key=True),
    db.Column('addon_id', db.Integer, db.ForeignKey('addon.id'), primary_key=True)
)

class SubscriptionTier(db.Model):
    """Clean subscription tier model - NO pricing, just tier structure"""
    __tablename__ = 'subscription_tier'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)  # "Solo Plan", "Team Plan"
    description = db.Column(db.Text, nullable=True)

    # Tier categorization for sorting/organization  
    tier_type = db.Column(db.String(32), nullable=False, default='monthly')  # 'monthly', 'yearly', 'promotion'

    # Core tier limits
    user_limit = db.Column(db.Integer, default=1, nullable=False)
    max_users = db.Column(db.Integer, nullable=True)  # Legacy field for compatibility
    max_recipes = db.Column(db.Integer, nullable=True)
    max_batches = db.Column(db.Integer, nullable=True)
    max_products = db.Column(db.Integer, nullable=True)
    max_batchbot_requests = db.Column(db.Integer, nullable=True)  # Future AI feature
    max_monthly_batches = db.Column(db.Integer, nullable=True)  # Monthly batch limit

    # Data retention policy (tier-driven)
    # Number of days to retain long-term data (recipes, batches, etc.) before hard delete (None = indefinite)
    data_retention_days = db.Column(db.Integer, nullable=True)
    # Days before deletion to start user notification campaign (e.g., 30)
    retention_notice_days = db.Column(db.Integer, nullable=True)
    # Optional: number of days a storage add-on purchase extends retention
    storage_addon_retention_days = db.Column(db.Integer, nullable=True)

    # Visibility control
    is_customer_facing = db.Column(db.Boolean, default=True, nullable=False)

    # Billing configuration - simplified
    billing_provider = db.Column(db.String(32), nullable=False, default='exempt')  # 'stripe', 'whop', 'exempt'

    # The ONLY external product links - stable lookup keys
    stripe_lookup_key = db.Column(db.String(128), nullable=True)
    # Optional storage add-on product (Stripe price lookup key) for retention extension
    stripe_storage_lookup_key = db.Column(db.String(128), nullable=True)
    whop_product_key = db.Column(db.String(128), nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    permissions = db.relationship('Permission', secondary=subscription_tier_permission,
                                 backref=db.backref('tiers', lazy='dynamic'))
    allowed_addons = db.relationship('Addon', secondary=tier_allowed_addon,
                                     backref=backref('allowed_on_tiers', lazy='dynamic'))

    # Explicitly named constraints to avoid SQLite batch mode issues
    __table_args__ = (
        db.UniqueConstraint('stripe_lookup_key', name='uq_subscription_tier_stripe_lookup_key'),
        db.UniqueConstraint('stripe_storage_lookup_key', name='uq_subscription_tier_stripe_storage_lookup_key'),
        db.UniqueConstraint('whop_product_key', name='uq_subscription_tier_whop_product_key'),
    )

    def get_permissions(self):
        """Get all permissions for this tier"""
        return [p.name for p in self.permissions]

    def get_permission_names(self):
        """Get permission names as a list"""
        return [p.name for p in self.permissions]

    def has_permission(self, permission_name):
        """Check if tier includes a specific permission"""
        if hasattr(permission_name, 'value'):
            permission_name = permission_name.value
        return any(p.name == permission_name for p in self.permissions)

    @property
    def key(self):
        """Generate key from name for backwards compatibility"""
        return self.name.lower().replace(' ', '_').replace('plan', '').strip('_')

    @property
    def is_billing_exempt(self):
        """Check if this tier is exempt from billing - single source of truth"""
        return self.billing_provider == 'exempt'

    @property
    def has_valid_integration(self):
        """Check if tier has valid billing integration"""
        if self.is_billing_exempt:
            return True
        # For non-exempt tiers, require proper integration
        if self.billing_provider == 'stripe':
            return bool(self.stripe_lookup_key)
        elif self.billing_provider == 'whop':
            return bool(self.whop_product_key)
        return False

    @property
    def requires_stripe_billing(self):
        """Compatibility property for legacy checks; maps to billing_provider."""
        return self.billing_provider == 'stripe'

    @property
    def requires_whop_billing(self):
        """Compatibility property for legacy checks; maps to billing_provider."""
        return self.billing_provider == 'whop'

    @property
    def can_be_deleted(self):
        """Check if this tier can be safely deleted"""
        return self.name.lower() not in ['exempt', 'free']  # Protect system tiers

    def __repr__(self):
        return f'<SubscriptionTier {self.name}>'