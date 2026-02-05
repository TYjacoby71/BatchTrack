"""Seed add-ons and backfill add-on permissions on tiers.

Synopsis:
Maintains the add-on catalog and aligns tier entitlements with add-on permissions.

Glossary:
- Add-on catalog: All purchasable/included entitlements.
- Backfill: Idempotent sync that reconciles tiers to add-ons.
"""

from app.extensions import db
from app.models.addon import Addon
from app.models import Permission, SubscriptionTier


# --- Seed add-on catalog ---
# Purpose: Upsert the add-on catalog rows.
def seed_addons():
    """Seed core add-ons used by the system (idempotent)."""
    core_addons = [
        {
            'key': 'recipe_variations',
            'name': 'Recipe Variations',
            'description': 'Enable master/variation/test versioning workflows',
            'permission_name': 'recipes.create_variations',
            'function_key': 'recipe_variations',
            'billing_type': 'subscription',
            'stripe_lookup_key': None,
            'batchbot_credit_amount': 0,
            'is_active': True
        },
        {
            'key': 'data_retention',
            'name': 'Data Retention',
            'description': 'Enable indefinite data retention while active',
            'permission_name': None,
            'function_key': 'retention',
            'billing_type': 'subscription',
            'stripe_lookup_key': 'data-retention',  # Set or override in prod as needed
            'batchbot_credit_amount': 0,
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
            'batchbot_credit_amount': 0,
            'is_active': True
        },
        {
            'key': 'batchbot_access',
            'name': 'Batchbot Access',
            'description': 'Enable the Batchbot assistant for your organization.',
            'permission_name': 'ai.batchbot',
            'function_key': 'batchbot_access',
            'billing_type': 'subscription',
            'stripe_lookup_key': None,
            'batchbot_credit_amount': 0,
            'is_active': True
        },
        {
            'key': 'batchbot_refill_100',
            'name': 'Batchley Refill - 100 Actions',
            'description': 'Adds 100 Batchley automation requests to the organization quota.',
            'permission_name': None,
            'function_key': 'batchbot_credits',
            'billing_type': 'one_time',
            'stripe_lookup_key': 'batchbot-refill-100',
            'batchbot_credit_amount': 100,
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
            existing.batchbot_credit_amount = data.get('batchbot_credit_amount', existing.batchbot_credit_amount or 0)
            existing.is_active = data['is_active']
        else:
            db.session.add(Addon(**data))

    db.session.commit()
    print('✅ Addons seeded')


# --- Backfill add-on permissions ---
# Purpose: Backfill tier entitlements for add-on permissions.
def backfill_addon_permissions():
    """Ensure add-on permissions are attached to tiers (idempotent)."""
    addons = Addon.query.filter_by(is_active=True).all()
    retention_addon = next((a for a in addons if a.function_key == 'retention'), None)
    perm_names = [a.permission_name for a in addons if a.permission_name]
    if not perm_names:
        print('ℹ️  No add-on permissions to backfill')
        return

    permissions = Permission.query.filter(
        Permission.is_active.is_(True),
        Permission.name.in_(perm_names),
    ).all()
    perm_by_name = {p.name: p for p in permissions}

    updated_tiers = 0
    for tier in SubscriptionTier.query.all():
        tier_perm_names = {p.name for p in tier.permissions}
        allowed_ids = {a.id for a in getattr(tier, 'allowed_addons', []) or []}
        included_ids = {a.id for a in getattr(tier, 'included_addons', []) or []}
        changed = False

        if retention_addon and getattr(tier, 'retention_policy', None) == 'subscribed':
            if retention_addon.id not in included_ids:
                tier.included_addons.append(retention_addon)
                included_ids.add(retention_addon.id)
                changed = True

        for addon in addons:
            perm_name = addon.permission_name
            if not perm_name:
                continue
            perm = perm_by_name.get(perm_name)
            if not perm:
                continue

            is_selected = addon.id in allowed_ids or addon.id in included_ids
            has_perm = perm_name in tier_perm_names

            if has_perm and not is_selected:
                tier.included_addons.append(addon)
                included_ids.add(addon.id)
                is_selected = True
                changed = True

            if is_selected and not has_perm:
                tier.permissions.append(perm)
                tier_perm_names.add(perm_name)
                changed = True

        if changed:
            updated_tiers += 1

    if updated_tiers:
        db.session.commit()
    print(f'✅ Add-on permission backfill complete (tiers updated: {updated_tiers})')

