
from datetime import datetime
from ..extensions import db

# Association table for subscription tier permissions
subscription_tier_permission = db.Table('subscription_tier_permission',
    db.Column('tier_id', db.Integer, db.ForeignKey('subscription_tier.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)

class SubscriptionTier(db.Model):
    """Clean subscription tier model - uses lookup keys, simple pricing from config"""
    __tablename__ = 'subscription_tier'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)  # "Solo Plan", "Team Plan"
    key = db.Column(db.String(32), nullable=False, unique=True)  # "solo", "team"
    description = db.Column(db.Text, nullable=True)

    # Core tier limits
    user_limit = db.Column(db.Integer, default=1, nullable=False)

    # Visibility control
    is_customer_facing = db.Column(db.Boolean, default=True, nullable=False)

    # Billing configuration - the RIGHT way
    billing_provider = db.Column(db.String(32), nullable=False, default='exempt')  # 'stripe', 'whop', 'exempt'
    is_billing_exempt = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # The ONLY external product links - stable lookup keys
    stripe_lookup_key = db.Column(db.String(128), nullable=True)
    whop_product_key = db.Column(db.String(128), nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    permissions = db.relationship('Permission', secondary=subscription_tier_permission,
                                 backref=db.backref('tiers', lazy='dynamic'))

    # Explicitly named constraints to avoid SQLite batch mode issues
    __table_args__ = (
        db.UniqueConstraint('stripe_lookup_key', name='uq_subscription_tier_stripe_lookup_key'),
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
    def is_exempt_from_billing(self):
        """Check if this tier is exempt from billing"""
        return self.billing_provider == 'exempt' or self.is_billing_exempt

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
        """Check if tier has valid billing integration"""
        if self.is_billing_exempt:
            return True
        return bool(self.stripe_lookup_key or self.whop_product_key)

    @property
    def can_be_deleted(self):
        """Check if this tier can be safely deleted"""
        return self.key != 'exempt'  # Protect system exempt tier

    def get_pricing_info(self):
        """Get pricing info from config file - simple and clean"""
        try:
            from ..blueprints.developer.subscription_tiers import load_tiers_config
            tiers_config = load_tiers_config()
            return tiers_config.get(self.key, {
                'name': self.name,
                'price_monthly': 0,
                'price_yearly': 0,
                'features': []
            })
        except Exception:
            # Minimal fallback - no complex pricing logic
            return {
                'name': self.name,
                'price_monthly': 0,
                'price_yearly': 0,
                'features': []
            }

    def __repr__(self):
        return f'<SubscriptionTier {self.name}>'
