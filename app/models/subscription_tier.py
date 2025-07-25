from datetime import datetime
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils

class SubscriptionTier(db.Model):
    """Database model for subscription tiers"""
    __tablename__ = 'subscription_tier'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)  # "Solo Plan", "Team Plan", etc.
    key = db.Column(db.String(32), nullable=False, unique=True)  # "solo", "team", etc.
    description = db.Column(db.Text, nullable=True)

    # Tier configuration
    user_limit = db.Column(db.Integer, default=1)  # -1 for unlimited
    is_customer_facing = db.Column(db.Boolean, default=True)
    is_available = db.Column(db.Boolean, default=True)

    # Stripe integration
    stripe_lookup_key = db.Column(db.String(128), nullable=True)
    fallback_price_monthly = db.Column(db.String(32), default='$0')
    fallback_price_yearly = db.Column(db.String(32), default='$0')
    stripe_price_monthly = db.Column(db.String(32), nullable=True)
    stripe_price_yearly = db.Column(db.String(32), nullable=True)
    last_synced = db.Column(db.DateTime, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    updated_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, onupdate=TimezoneUtils.utc_now)

    # Relationships - simplified to just organizations and permissions
    organizations = db.relationship('Organization', backref='tier', lazy='dynamic')
    permissions = db.relationship('Permission', secondary='subscription_tier_permission', 
                                 backref=db.backref('tiers', lazy='dynamic'))

    @property
    def effective_price_monthly(self):
        """Get effective monthly price (Stripe if available, fallback otherwise)"""
        return self.stripe_price_monthly or self.fallback_price_monthly

    @property
    def effective_price_yearly(self):
        """Get effective yearly price (Stripe if available, fallback otherwise)"""
        return self.stripe_price_yearly or self.fallback_price_yearly

    @property
    def is_stripe_ready(self):
        """Check if tier is properly configured for Stripe"""
        return bool(self.stripe_lookup_key and self.stripe_price_monthly)

    def get_permissions(self):
        """Get all permissions for this tier"""
        return [p.name for p in self.permissions]

    def has_permission(self, permission_name):
        """Check if tier includes a specific permission"""
        return any(p.name == permission_name for p in self.permissions)

    def __repr__(self):
        return f'<SubscriptionTier {self.key}: {self.name}>'

# Association table for tier permissions
subscription_tier_permission = db.Table('subscription_tier_permission',
    db.Column('tier_id', db.Integer, db.ForeignKey('subscription_tier.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)