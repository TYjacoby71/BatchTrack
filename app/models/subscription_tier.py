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
    requires_stripe_billing = db.Column(db.Boolean, default=True)  # False for exempt, free, or internal tiers
    
    # Pricing structure
    billing_cycle = db.Column(db.String(16), default='monthly')  # monthly, yearly, lifetime
    pricing_category = db.Column(db.String(32), default='standard')  # standard, promotional, enterprise
    price_amount = db.Column(db.Numeric(10, 2), nullable=True)  # Single price for this tier
    currency = db.Column(db.String(3), default='USD')

    # Stripe integration
    stripe_lookup_key = db.Column(db.String(128), nullable=True)
    stripe_customer_id = db.Column(db.String(128), nullable=True)
    stripe_subscription_id = db.Column(db.String(128), nullable=True)
    stripe_price_id = db.Column(db.String(128), nullable=True)  # Single price ID for this tier
    fallback_price = db.Column(db.String(32), default='$0')
    stripe_price = db.Column(db.String(32), nullable=True)
    last_synced = db.Column(db.DateTime, nullable=True)

    # Subscription status and billing info
    status = db.Column(db.String(32), default='inactive')  # active, trialing, canceled, etc.
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    next_billing_date = db.Column(db.DateTime, nullable=True)
    trial_start = db.Column(db.DateTime, nullable=True)
    trial_end = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, default=False)

    # Metadata
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    updated_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, onupdate=TimezoneUtils.utc_now)

    # Relationships
    permissions = db.relationship('Permission', secondary='subscription_tier_permission', 
                                 backref=db.backref('tiers', lazy='dynamic'))

    @property
    def effective_price(self):
        """Get price from Stripe or fallback"""
        return self.stripe_price or self.fallback_price
    
    @property
    def display_price(self):
        """Get formatted price for display"""
        price = self.effective_price
        if price and price.startswith('$'):
            return price
        elif self.price_amount:
            return f"${self.price_amount:.0f}"
        return self.fallback_price

    def get_permissions(self):
        """Get all permissions for this tier"""
        return [p.name for p in self.permissions]

    def has_permission(self, permission_name):
        """Check if tier includes a specific permission"""
        return any(p.name == permission_name for p in self.permissions)

    @property
    def is_exempt_from_billing(self):
        """Check if this tier is exempt from billing"""
        return not self.requires_stripe_billing

    @property
    def is_stripe_billing_required(self):
        """Check if this tier requires Stripe billing (alias for clarity)"""
        return self.requires_stripe_billing

    @property
    def can_be_deleted(self):
        """Check if this tier can be safely deleted"""
        # Don't allow deletion of exempt tier (system dependency)
        if self.key == 'exempt':
            return False
        # Allow deletion of other tiers including free
        return True

    def __repr__(self):
        return f'<SubscriptionTier {self.key}: {self.name}>'

# Association table for tier permissions
subscription_tier_permission = db.Table('subscription_tier_permission',
    db.Column('tier_id', db.Integer, db.ForeignKey('subscription_tier.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)