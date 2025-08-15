from datetime import datetime
from ..extensions import db
from sqlalchemy.ext.hybrid import hybrid_property

class SubscriptionTier(db.Model):
    """Database model for subscription tiers - authorization and tier definition only"""
    __tablename__ = 'subscription_tier'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)  # "Solo Plan", "Team Plan", etc.
    key = db.Column(db.String(32), nullable=False, unique=True)  # "solo", "team", etc.

    description = db.Column(db.Text, nullable=True)

    # Core, flexible fields (modern approach)
    stripe_product_id = db.Column(db.String(128), nullable=True)
    stripe_price_id = db.Column(db.String(128), nullable=True)

    # Legacy/test compatibility fields (nullable; for backwards compatibility)
    stripe_price_id_monthly = db.Column(db.String(128), nullable=True)
    stripe_price_id_yearly = db.Column(db.String(128), nullable=True)

    # Tier configuration
    user_limit = db.Column(db.Integer, default=1)  # -1 for unlimited
    max_users = db.Column(db.Integer, default=1, nullable=False)  # For test compatibility
    max_monthly_batches = db.Column(db.Integer, default=0, nullable=False)  # For test compatibility
    
    # Simplified visibility - only customer_facing needed now
    is_customer_facing = db.Column(db.Boolean, default=True)

    # NEW: Billing configuration - cleaner approach
    billing_provider = db.Column(db.String(32), nullable=False, default='exempt')  # 'stripe', 'whop', 'exempt'
    is_billing_exempt = db.Column(db.Boolean, default=False, index=True)  # Override to bypass billing checks

    # Integration keys for linking to external products (required unless exempt)
    stripe_lookup_key = db.Column(db.String(128), nullable=True, unique=True)  # Links to Stripe product
    whop_product_key = db.Column(db.String(128), nullable=True, unique=True)   # Links to Whop product

    # Pricing for display and offline use
    fallback_price = db.Column(db.String(32), default='$0')

    # Offline support
    last_billing_sync = db.Column(db.DateTime, nullable=True)  # When billing was last verified
    grace_period_days = db.Column(db.Integer, default=7)  # Days to allow offline usage

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    permissions = db.relationship('Permission', secondary='subscription_tier_permission',
                                 backref=db.backref('tiers', lazy='dynamic'))

    def get_permissions(self):
        """Get all permissions for this tier"""
        return [p.name for p in self.permissions]

    def has_permission(self, permission_name):
        """Check if tier includes a specific permission"""
        # Handle enum permission names by converting to string
        if hasattr(permission_name, 'value'):
            permission_name = permission_name.value
        return any(p.name == permission_name for p in self.permissions)

    @property
    def is_exempt_from_billing(self):
        """Check if this tier is exempt from billing"""
        return self.billing_provider == 'exempt' or self.is_billing_exempt

    @property
    def requires_billing_check(self):
        """Check if this tier requires billing verification"""
        return not self.is_exempt_from_billing and self.billing_provider in ['stripe', 'whop']

    @property
    def requires_stripe_billing(self):
        """Check if this tier requires Stripe billing verification"""
        return self.billing_provider == 'stripe' and not self.is_billing_exempt

    @property
    def requires_whop_billing(self):
        """Check if this tier requires Whop billing verification"""
        return self.billing_provider == 'whop' and not self.is_billing_exempt

    @property
    def has_valid_integration(self):
        """Check if tier has valid integration setup"""
        if self.is_exempt_from_billing:
            return True
        
        if self.billing_provider == 'stripe':
            return bool(self.stripe_lookup_key)
        elif self.billing_provider == 'whop':
            return bool(self.whop_product_key)
        
        return False

    @property
    def can_be_deleted(self):
        """Check if this tier can be safely deleted"""
        # Don't allow deletion of exempt tier (system dependency)
        if self.key == 'exempt':
            return False
        return True

    @property
    def effective_price_id(self):
        """Get the effective price ID, preferring modern single price over legacy monthly"""
        return self.stripe_price_id or self.stripe_price_id_monthly

    # Legacy compatibility properties
    @property
    def is_available(self):
        """Legacy compatibility - maps to is_customer_facing"""
        return self.is_customer_facing

    @property
    def tier_type(self):
        """Legacy compatibility - derive from billing_provider"""
        if self.billing_provider == 'exempt' or self.is_billing_exempt:
            return 'exempt'
        return 'paid'

    @classmethod
    def get_by_key(cls, key: str):
        return cls.query.filter_by(tier_key=key).first()

    def __repr__(self):
        return f'<SubscriptionTier {self.name}>'

# Association table for tier permissions
subscription_tier_permission = db.Table('subscription_tier_permission',
    db.Column('tier_id', db.Integer, db.ForeignKey('subscription_tier.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)