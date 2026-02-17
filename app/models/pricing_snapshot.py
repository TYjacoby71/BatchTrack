from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils


class PricingSnapshot(db.Model):
    """Stores snapshots of Stripe pricing data for resilience"""

    __tablename__ = "pricing_snapshots"

    id = db.Column(db.Integer, primary_key=True)

    # Stripe identifiers
    stripe_price_id = db.Column(db.String(128), nullable=False, unique=True)
    stripe_lookup_key = db.Column(db.String(64), nullable=False)
    stripe_product_id = db.Column(db.String(128), nullable=False)

    # Pricing data
    unit_amount = db.Column(db.Integer, nullable=False)  # Amount in cents
    currency = db.Column(db.String(3), default="usd")
    interval = db.Column(db.String(16), nullable=False)  # month, year
    interval_count = db.Column(db.Integer, default=1)

    # Product metadata
    product_name = db.Column(db.String(128), nullable=False)
    product_description = db.Column(db.Text, nullable=True)
    features = db.Column(db.Text, nullable=True)  # JSON string of features

    # Snapshot metadata
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    last_stripe_sync = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    @property
    def amount_dollars(self):
        """Get amount in dollars from unit_amount (cents)"""
        if not self.unit_amount:
            return 0.0
        return self.unit_amount / 100.0

    @property
    def features_list(self):
        """Get features as a list from the stored string"""
        if not self.features:
            return []
        return [f.strip() for f in self.features.split("\n") if f.strip()]

    @classmethod
    def get_latest_for_tier(cls, tier_key):
        """Get the latest pricing snapshot for a specific tier"""
        return (
            cls.query.filter_by(stripe_lookup_key=tier_key, is_active=True)
            .order_by(cls.last_stripe_sync.desc())
            .first()
        )

    @classmethod
    def update_from_stripe_data(cls, stripe_price, stripe_product):
        """Update or create pricing snapshot from Stripe data"""
        snapshot = cls.query.filter_by(stripe_price_id=stripe_price.id).first()

        if not snapshot:
            snapshot = cls(stripe_price_id=stripe_price.id)
            db.session.add(snapshot)

        # Update snapshot data
        snapshot.stripe_lookup_key = getattr(stripe_price, "lookup_key", "")
        snapshot.stripe_product_id = stripe_price.product
        snapshot.unit_amount = stripe_price.unit_amount
        snapshot.currency = stripe_price.currency
        snapshot.interval = (
            stripe_price.recurring.interval if stripe_price.recurring else None
        )
        snapshot.interval_count = (
            stripe_price.recurring.interval_count if stripe_price.recurring else None
        )
        snapshot.product_name = stripe_product.name
        snapshot.product_description = stripe_product.description
        snapshot.features = stripe_product.metadata.get("features", "")
        snapshot.last_stripe_sync = TimezoneUtils.utc_now()
        snapshot.is_active = True

        return snapshot

    @classmethod
    def get_latest_pricing(cls, lookup_key):
        """Get the most recent pricing snapshot for a lookup key"""
        return (
            cls.query.filter_by(stripe_lookup_key=lookup_key, is_active=True)
            .order_by(cls.last_stripe_sync.desc())
            .first()
        )
