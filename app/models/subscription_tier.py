from datetime import datetime
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils

class SubscriptionTier(db.Model):
    """Database model for subscription tiers - authorization and tier definition only"""
    __tablename__ = 'subscription_tier'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)  # "Solo Plan", "Team Plan", etc.
    key = db.Column(db.String(32), nullable=False, unique=True)  # "solo", "team", etc.
    
    # NEW: stable programmatic key the app/tests expect
    tier_key = db.Column(db.String(64), unique=True, nullable=True, index=True)
    
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
    is_customer_facing = db.Column(db.Boolean, default=True)
    is_available = db.Column(db.Boolean, default=True)
    
    # Tier type determines billing behavior
    tier_type = db.Column(db.String(32), default='paid')  # 'paid', 'exempt', 'internal', 'trial'
    
    # Billing provider specifies which system to check for paid tiers
    billing_provider = db.Column(db.String(32), nullable=True)  # 'stripe', 'whop', or None

    # Integration keys for linking to external products
    stripe_lookup_key = db.Column(db.String(128), nullable=True)  # Links to Stripe product
    whop_product_key = db.Column(db.String(128), nullable=True)   # Links to Whop product

    # Pricing for display and offline use
    fallback_price = db.Column(db.String(32), default='$0')

    # Offline support
    last_billing_sync = db.Column(db.DateTime, nullable=True)  # When billing was last verified
    grace_period_days = db.Column(db.Integer, default=7)  # Days to allow offline usage

    # Metadata
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    updated_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, onupdate=TimezoneUtils.utc_now)

    # Relationships
    permissions = db.relationship('Permission', secondary='subscription_tier_permission',
                                 backref=db.backref('tiers', lazy='dynamic'))

    def get_permissions(self):
        """Get all permissions for this tier"""
        return [p.name for p in self.permissions]

    def has_permission(self, permission_name):
        """Check if tier includes a specific permission"""
        return any(p.name == permission_name for p in self.permissions)

    @property
    def is_exempt_from_billing(self):
        """Check if this tier is exempt from billing"""
        return self.tier_type in ['exempt', 'internal']
    
    @property
    def requires_billing_check(self):
        """Check if this tier requires billing verification"""
        return self.tier_type == 'paid' and self.billing_provider is not None

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

    @classmethod
    def get_by_key(cls, key: str):
        return cls.query.filter_by(tier_key=key).first()

    def __repr__(self):
        return f'<SubscriptionTier {self.key}: {self.name}>'

# Association table for tier permissions
subscription_tier_permission = db.Table('subscription_tier_permission',
    db.Column('tier_id', db.Integer, db.ForeignKey('subscription_tier.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)