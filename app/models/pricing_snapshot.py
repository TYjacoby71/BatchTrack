
from datetime import datetime
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
import json

class PricingSnapshot(db.Model):
    """Stores snapshots of Stripe pricing data for resilience"""
    __tablename__ = 'pricing_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Stripe identifiers
    stripe_price_id = db.Column(db.String(128), nullable=False, unique=True)
    stripe_lookup_key = db.Column(db.String(64), nullable=False)
    stripe_product_id = db.Column(db.String(128), nullable=False)
    
    # Pricing data
    unit_amount = db.Column(db.Integer, nullable=False)  # Amount in cents
    currency = db.Column(db.String(3), default='usd')
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
        """Get amount in dollars"""
        return self.unit_amount / 100
    
    @property
    def features_list(self):
        """Get features as a list"""
        if not self.features:
            return []
        try:
            return json.loads(self.features)
        except:
            return []
    
    @classmethod
    def get_latest_pricing(cls, lookup_key):
        """Get the most recent pricing snapshot for a lookup key"""
        return cls.query.filter_by(
            stripe_lookup_key=lookup_key,
            is_active=True
        ).order_by(cls.last_stripe_sync.desc()).first()
    
    @classmethod
    def update_from_stripe_data(cls, price_data, product_data):
        """Update or create pricing snapshot from Stripe data"""
        snapshot = cls.query.filter_by(
            stripe_price_id=price_data['id']
        ).first()
        
        if not snapshot:
            snapshot = cls(stripe_price_id=price_data['id'])
            db.session.add(snapshot)
        
        # Update with latest data
        snapshot.stripe_lookup_key = price_data.get('lookup_key') or None
        snapshot.stripe_product_id = price_data['product']
        snapshot.unit_amount = price_data['unit_amount']
        snapshot.currency = price_data['currency']
        snapshot.interval = price_data['recurring']['interval']
        snapshot.interval_count = price_data['recurring']['interval_count']
        snapshot.product_name = product_data['name']
        snapshot.product_description = product_data.get('description', '')
        
        # Store features as JSON
        if product_data.get('metadata', {}).get('features'):
            features = product_data['metadata']['features'].split(',')
            snapshot.features = json.dumps([f.strip() for f in features])
        
        snapshot.last_stripe_sync = TimezoneUtils.utc_now()
        
        return snapshot
