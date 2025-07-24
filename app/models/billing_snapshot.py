
from datetime import datetime, timedelta
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils

class BillingSnapshot(db.Model):
    """Stores snapshots of confirmed billing states for resilience"""
    __tablename__ = 'billing_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    
    # Confirmed billing state from Stripe
    confirmed_tier = db.Column(db.String(32), nullable=False)
    confirmed_status = db.Column(db.String(32), nullable=False)  # active, trialing, etc.
    
    # Billing period this snapshot covers
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    
    # Stripe data at time of snapshot
    stripe_subscription_id = db.Column(db.String(128), nullable=True)
    stripe_customer_id = db.Column(db.String(128), nullable=True)
    
    # Grace period calculation
    grace_period_days = db.Column(db.Integer, default=3)  # Extra days after period_end
    
    # Snapshot metadata
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    last_stripe_sync = db.Column(db.DateTime, nullable=False)
    sync_source = db.Column(db.String(64), default='webhook')  # webhook, manual, etc.
    
    # Relationships
    organization = db.relationship('Organization', backref='billing_snapshots')
    
    @property
    def is_valid_for_access(self):
        """Check if this snapshot allows access (within grace period)"""
        now = TimezoneUtils.utc_now()
        grace_end = self.period_end + timedelta(days=self.grace_period_days)
        
        # Allow access if:
        # 1. We're in the confirmed billing period, OR
        # 2. We're in the grace period after the billing period
        return now <= grace_end
    
    @property
    def days_until_grace_expires(self):
        """Get days remaining in grace period"""
        now = TimezoneUtils.utc_now()
        grace_end = self.period_end + timedelta(days=self.grace_period_days)
        
        if now > grace_end:
            return 0
        
        return (grace_end - now).days
    
    @classmethod
    def get_latest_valid_snapshot(cls, organization_id):
        """Get the most recent valid billing snapshot for an organization"""
        return cls.query.filter_by(
            organization_id=organization_id
        ).filter(
            cls.period_end + timedelta(days=cls.grace_period_days) >= TimezoneUtils.utc_now()
        ).order_by(cls.created_at.desc()).first()
    
    @classmethod
    def create_from_subscription(cls, subscription):
        """Create a billing snapshot from current subscription state"""
        if not subscription.current_period_start or not subscription.current_period_end:
            return None
            
        snapshot = cls(
            organization_id=subscription.organization_id,
            confirmed_tier=subscription.tier,
            confirmed_status=subscription.status,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            stripe_subscription_id=subscription.stripe_subscription_id,
            stripe_customer_id=subscription.stripe_customer_id,
            last_stripe_sync=TimezoneUtils.utc_now()
        )
        
        db.session.add(snapshot)
        return snapshot
