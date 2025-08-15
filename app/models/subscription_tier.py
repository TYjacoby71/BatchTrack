
from datetime import datetime
from ..extensions import db

class SubscriptionTier(db.Model):
    """Clean subscription tier model - uses lookup keys, not hardcoded price IDs"""
    __tablename__ = 'subscription_tier'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)  # "Solo Plan", "Team Plan"
    key = db.Column(db.String(32), nullable=False, unique=True)  # "solo", "team"
    description = db.Column(db.Text, nullable=True)
    
    # Core tier limits
    user_limit = db.Column(db.Integer, default=1, nullable=False)
    max_users = db.Column(db.Integer, default=1, nullable=False)  # Compatibility
    max_monthly_batches = db.Column(db.Integer, default=0, nullable=False)  # Compatibility
    
    # Visibility control
    is_customer_facing = db.Column(db.Boolean, default=True, nullable=False)
    
    # Billing configuration - the RIGHT way
    billing_provider = db.Column(db.String(32), nullable=False, default='exempt')  # 'stripe', 'whop', 'exempt'
    is_billing_exempt = db.Column(db.Boolean, default=False, nullable=False, index=True)
    
    # The ONLY external product links - stable lookup keys
    stripe_lookup_key = db.Column(db.String(128), nullable=True, unique=True)  # e.g. "solo_plan"
    whop_product_key = db.Column(db.String(128), nullable=True, unique=True)
    
    # Display-only pricing (fallback when offline)
    fallback_price = db.Column(db.String(32), default='$0')
    
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
        return self.key != 'exempt'  # Protect system exempt tier

    def __repr__(self):
        return f'<SubscriptionTier {self.name}>'

# Association table for tier permissions
subscription_tier_permission = db.Table('subscription_tier_permission',
    db.Column('tier_id', db.Integer, db.ForeignKey('subscription_tier.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)
