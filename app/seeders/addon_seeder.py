from app.extensions import db
from app.models.addon import Addon


def seed_addons():
    """Seed core add-ons used by the system (idempotent)."""
    core_addons = [
        {
            'key': 'storage',
            'name': 'Extra Data Storage',
            'description': 'Extend data retention and storage capacity',
            'permission_name': 'storage.extend',
            'function_key': 'retention',
            'billing_type': 'subscription',
            'stripe_lookup_key': None,  # Set in environment-specific config/UI later
            'retention_extension_days': 365,
            'is_active': True
        },
        {
            'key': 'advanced_analytics',
            'name': 'Advanced Analytics',
            'description': 'Unlock business intelligence and advanced reports',
            'permission_name': 'reports.analytics',
            'function_key': 'analytics',
            'billing_type': 'subscription',
            'stripe_lookup_key': None,
            'is_active': True
        }
    ]

    for data in core_addons:
        existing = Addon.query.filter_by(key=data['key']).first()
        if existing:
            # Update selected fields to keep idempotent
            existing.name = data['name']
            existing.description = data['description']
            existing.permission_name = data['permission_name']
            existing.function_key = data.get('function_key')
            existing.billing_type = data['billing_type']
            # Do not overwrite stripe_lookup_key if already set in prod
            if not existing.stripe_lookup_key:
                existing.stripe_lookup_key = data['stripe_lookup_key']
            if data.get('retention_extension_days') is not None and not getattr(existing, 'retention_extension_days', None):
                existing.retention_extension_days = data['retention_extension_days']
            existing.is_active = data['is_active']
        else:
            db.session.add(Addon(**data))

    db.session.commit()
    print('✅ Addons seeded')

