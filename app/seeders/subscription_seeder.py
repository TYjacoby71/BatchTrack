#!/usr/bin/env python3
"""Seed subscription tiers and data"""

import json
import os
from flask import current_app
from ..models import db, Organization, SubscriptionTier, Permission
from datetime import datetime

def create_exempt_tier():
    """Create the only hardcoded tier - exempt tier for system use"""
    exempt_tier = SubscriptionTier.query.filter_by(key='exempt').first()

    if not exempt_tier:
        print("✅ Creating exempt tier")
        exempt_tier = SubscriptionTier(
            key='exempt',
            name='Exempt Plan',
            description='System tier for exempt accounts - unlimited access',
            user_limit=-1,  # Unlimited users
            is_customer_facing=False,
            is_available=True,
            stripe_lookup_key='',
            fallback_price_monthly='$0',
            fallback_price_yearly='$0',
            stripe_price_monthly='Exempt',
            stripe_price_yearly='Exempt'
        )
        db.session.add(exempt_tier)

        # Give exempt tier ALL permissions
        all_permissions = Permission.query.all()
        exempt_tier.permissions = all_permissions

        db.session.commit()
        print(f"   - Exempt tier created with {len(all_permissions)} permissions")
    else:
        print("ℹ️  Exempt tier already exists")
        # Ensure it has all permissions
        all_permissions = Permission.query.all()
        exempt_tier.permissions = all_permissions
        db.session.commit()

    return exempt_tier

def load_subscription_tiers():
    """Load subscription tiers from JSON file if it exists"""
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'subscription_tiers.json')

    if not os.path.exists(json_path):
        print("ℹ️  No subscription_tiers.json found - only exempt tier will be created")
        return {}

    with open(json_path, 'r') as f:
        return json.load(f)

def seed_subscription_tiers():
    """Create subscription tier records from JSON configuration (optional) - ONLY creates new tiers, preserves existing"""
    if not current_app:
        raise RuntimeError("seed_subscription_tiers() must be called within Flask application context")

    print("=== Seeding Subscription Tiers (Create Only Mode) ===")

    # Always create exempt tier first
    create_exempt_tier()

    # Load additional tiers from JSON if available
    tiers_data = load_subscription_tiers()

    # Skip exempt tier if it's in JSON - we handle it separately
    if 'exempt' in tiers_data:
        del tiers_data['exempt']

    for tier_key, tier_config in tiers_data.items():
        # Skip metadata keys (they start with underscore)
        if tier_key.startswith('_'):
            print(f"ℹ️  Skipping metadata key: {tier_key}")
            continue

        # Skip if tier_config is not a dictionary
        if not isinstance(tier_config, dict):
            print(f"⚠️  Skipping invalid tier config for {tier_key}: {type(tier_config)}")
            continue

        # Check if tier already exists - SKIP if it does to preserve user modifications
        existing_tier = SubscriptionTier.query.filter_by(key=tier_key).first()

        if existing_tier:
            print(f"ℹ️  Tier '{tier_key}' already exists - PRESERVING existing configuration")
            continue  # Skip to preserve user modifications

        # Only create NEW tiers from JSON
        print(f"✅ Creating new tier from JSON: {tier_key}")
        tier = SubscriptionTier(key=tier_key)
        db.session.add(tier)

        # Set tier properties from JSON for NEW tiers only
        tier.name = tier_config.get('name', tier_key.title())
        tier.description = tier_config.get('description', '')
        tier.user_limit = tier_config.get('user_limit', 1)
        tier.is_customer_facing = tier_config.get('is_customer_facing', True)
        tier.is_available = tier_config.get('is_available', True)
        tier.stripe_lookup_key = tier_config.get('stripe_lookup_key', '')
        tier.fallback_price_monthly = tier_config.get('fallback_price_monthly', '$0')
        tier.fallback_price_yearly = tier_config.get('fallback_price_yearly', '$0')
        tier.stripe_price_monthly = tier_config.get('stripe_price_monthly')
        tier.stripe_price_yearly = tier_config.get('stripe_price_yearly')

        # Assign permissions for NEW tiers only
        permission_names = tier_config.get('permissions', [])
        permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
        tier.permissions = permissions

        print(f"   - {len(permissions)} permissions assigned to new tier")

    db.session.commit()
    print("✅ Subscription tiers seeded successfully!")
    print("   - Existing tiers were PRESERVED and not modified")
    print("   - Only new tiers were created from JSON configuration")

def migrate_existing_organizations():
    """Migrate existing organizations to use tier IDs"""
    if not current_app:
        raise RuntimeError("migrate_existing_organizations() must be called within Flask application context")

    print("=== Migrating Organizations to Tier IDs ===")

    organizations = Organization.query.all()

    for org in organizations:
        if not org.subscription_tier_id:
            # Assign exempt tier to any organization without a tier
            exempt_tier = SubscriptionTier.query.filter_by(key='exempt').first()
            if exempt_tier:
                org.subscription_tier_id = exempt_tier.id
                print(f"✅ Assigned exempt tier to organization {org.name}")

    db.session.commit()
    print("✅ Organization migration completed!")

def force_sync_tiers_from_json():
    """FORCE sync all tiers from JSON - OVERWRITES existing tiers (use with caution)"""
    if not current_app:
        raise RuntimeError("force_sync_tiers_from_json() must be called within Flask application context")

    print("=== FORCE SYNCING Subscription Tiers from JSON (OVERWRITES EXISTING) ===")
    print("⚠️  WARNING: This will overwrite existing tier configurations!")

    # Always create exempt tier first
    create_exempt_tier()

    # Load additional tiers from JSON if available
    tiers_data = load_subscription_tiers()

    # Skip exempt tier if it's in JSON - we handle it separately
    if 'exempt' in tiers_data:
        del tiers_data['exempt']

    for tier_key, tier_config in tiers_data.items():
        # Skip metadata keys (they start with underscore)
        if tier_key.startswith('_'):
            print(f"ℹ️  Skipping metadata key: {tier_key}")
            continue

        # Skip if tier_config is not a dictionary
        if not isinstance(tier_config, dict):
            print(f"⚠️  Skipping invalid tier config for {tier_key}: {type(tier_config)}")
            continue

        # Find or create tier record (FORCE mode)
        existing_tier = SubscriptionTier.query.filter_by(key=tier_key).first()

        if existing_tier:
            print(f"🔄 FORCE updating existing tier: {tier_key}")
            tier = existing_tier
        else:
            print(f"✅ Creating new tier: {tier_key}")
            tier = SubscriptionTier(key=tier_key)
            db.session.add(tier)

        # FORCE update tier properties from JSON
        tier.name = tier_config.get('name', tier_key.title())
        tier.description = tier_config.get('description', '')
        tier.user_limit = tier_config.get('user_limit', 1)
        tier.is_customer_facing = tier_config.get('is_customer_facing', True)
        tier.is_available = tier_config.get('is_available', True)
        tier.stripe_lookup_key = tier_config.get('stripe_lookup_key', '')
        tier.fallback_price_monthly = tier_config.get('fallback_price_monthly', '$0')
        tier.fallback_price_yearly = tier_config.get('fallback_price_yearly', '$0')
        tier.stripe_price_monthly = tier_config.get('stripe_price_monthly')
        tier.stripe_price_yearly = tier_config.get('stripe_price_yearly')

        # FORCE assign permissions
        permission_names = tier_config.get('permissions', [])
        permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
        tier.permissions = permissions

        print(f"   - {len(permissions)} permissions assigned")

    db.session.commit()
    print("✅ FORCE sync completed - all tiers updated from JSON!")

def seed_subscriptions():
    """Seed subscription tiers only - organizations are created by user seeder"""
    from flask import current_app

    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_subscriptions() must be called within Flask application context")

    print("=== Seeding Subscription Tiers Only ===")

    # Step 1: Create tier records (exempt + any NEW from JSON, preserves existing)
    seed_subscription_tiers()

    # Step 2: Migrate existing organizations if any exist
    migrate_existing_organizations()

    print("✅ Subscription tiers seeding completed!")
    print("   - Exempt tier created with unlimited permissions")
    print("   - New tiers created from JSON configuration")
    print("   - Existing tier configurations were PRESERVED")
    print("   - Ready for user seeder to create organizations")