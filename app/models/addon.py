from datetime import datetime, timezone
from ..extensions import db


class Addon(db.Model):
    __tablename__ = 'addon'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Permission this addon grants when active
    permission_name = db.Column(db.String(128), nullable=True)

    # Optional function key this addon enables (e.g., 'retention', 'analytics')
    function_key = db.Column(db.String(64), nullable=True)

    # If this addon extends data retention, specify how many days to extend
    retention_extension_days = db.Column(db.Integer, nullable=True)

    # Billing integration
    billing_type = db.Column(db.String(32), nullable=False, default='subscription')  # 'subscription' | 'one_time'
    stripe_lookup_key = db.Column(db.String(128), nullable=True)
    batchbot_credit_amount = db.Column(db.Integer, nullable=False, default=0)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class OrganizationAddon(db.Model):
    __tablename__ = 'organization_addon'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False, index=True)
    addon_id = db.Column(db.Integer, db.ForeignKey('addon.id'), nullable=False, index=True)

    active = db.Column(db.Boolean, default=True, nullable=False)
    source = db.Column(db.String(32), nullable=False, default='subscription_item')  # subscription_item | one_time
    stripe_item_id = db.Column(db.String(128), nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    addon = db.relationship('Addon')
