from datetime import datetime, timedelta
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils

class Subscription(db.Model):
    """Flexible subscription management separate from organization"""
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

    # Core subscription info
    tier = db.Column(db.String(32), default='free')  # free, solo, team, enterprise, exempt
    status = db.Column(db.String(32), default='active')  # active, trialing, past_due, canceled, paused

    # Flexible period management
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    next_billing_date = db.Column(db.DateTime, nullable=True)

    # Trial handling (managed by Stripe)
    trial_start = db.Column(db.DateTime, nullable=True)
    trial_end = db.Column(db.DateTime, nullable=True)

    # Payment processor integration
    stripe_subscription_id = db.Column(db.String(128), nullable=True)
    stripe_customer_id = db.Column(db.String(128), nullable=True)

    # Flexibility for discounts/comps
    discount_percent = db.Column(db.Float, default=0)  # 0-100
    discount_end_date = db.Column(db.DateTime, nullable=True)
    comp_months_remaining = db.Column(db.Integer, default=0)

    # Metadata
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    updated_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, onupdate=TimezoneUtils.utc_now)
    notes = db.Column(db.Text, nullable=True)  # For internal tracking

    # Relationships
    organization = db.relationship('Organization', backref='subscription')

    @property
    def is_trial(self):
        """Check if currently in trial period (from Stripe)"""
        return self.status == 'trialing'

    @property
    def is_active(self):
        """Check if subscription allows access"""
        if self.status == 'canceled':
            return False
        if self.tier == 'exempt':  # Exempt tier always has access
            return True
        if self.is_trial:
            return True
        return self.status in ['active', 'trialing']

    @property
    def effective_tier(self):
        """Get the tier considering trial status"""
        if self.tier == 'exempt':
            return 'enterprise'  # Exempt accounts get enterprise features
        return self.tier

    def extend_trial(self, days, reason=None):
        """Extend trial period"""
        if not self.trial_end:
            return False

        self.trial_end += timedelta(days=days)
        if reason:
            self.notes = f"{self.notes or ''}\nTrial extended {days} days: {reason}".strip()
        db.session.commit()
        return True

    def add_comp_months(self, months, reason=None):
        """Add complimentary months"""
        self.comp_months_remaining += months
        if reason:
            self.notes = f"{self.notes or ''}\nAdded {months} comp months: {reason}".strip()
        db.session.commit()

    def apply_discount(self, percent, end_date=None, reason=None):
        """Apply percentage discount"""
        self.discount_percent = percent
        self.discount_end_date = end_date
        if reason:
            self.notes = f"{self.notes or ''}\nDiscount applied {percent}%: {reason}".strip()
        db.session.commit()