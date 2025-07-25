
#!/usr/bin/env python3
"""Seed subscription tiers and data"""

import json
import os
from flask import current_app
from ..models import db, Organization, Subscription, SubscriptionTier, Permission
from datetime import datetime

def load_subscription_tiers():
    """Load subscription tiers from JSON file"""
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'subscription_tiers.json')
    with open(json_path, 'r') as f:
        return json.load(f)

def seed_subscription_tiers():
    """Create subscription tier records from JSON configuration"""
    if not current_app:
        raise RuntimeError("seed_subscription_tiers() must be called within Flask application context")
    
    print("=== Seeding Subscription Tiers ===")
    
    # Load tiers from JSON
    tiers_data = load_subscription_tiers()
    
    for tier_key, tier_config in tiers_data.items():
        # Check if tier already exists
        existing_tier = SubscriptionTier.query.filter_by(key=tier_key).first()
        
        if existing_tier:
            print(f"ℹ️  Updating existing tier: {tier_key}")
            tier = existing_tier
        else:
            print(f"✅ Creating new tier: {tier_key}")
            tier = SubscriptionTier(key=tier_key)
            db.session.add(tier)
        
        # Update tier properties
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
        
        # Assign permissions
        permission_names = tier_config.get('permissions', [])
        permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
        tier.permissions = permissions
        
        print(f"   - {len(permissions)} permissions assigned")
    
    db.session.commit()
    print("✅ Subscription tiers seeded successfully!")

def migrate_existing_organizations():
    """Migrate existing organizations to use tier IDs"""
    if not current_app:
        raise RuntimeError("migrate_existing_organizations() must be called within Flask application context")
    
    print("=== Migrating Organizations to Tier IDs ===")
    
    organizations = Organization.query.all()
    
    for org in organizations:
        if org.subscription_tier and not org.subscription_tier_id:
            # Find matching tier by key
            tier = SubscriptionTier.query.filter_by(key=org.subscription_tier).first()
            if tier:
                org.subscription_tier_id = tier.id
                print(f"✅ Migrated organization {org.name} to tier ID {tier.id} ({tier.key})")
            else:
                print(f"⚠️  No tier found for organization {org.name} with tier '{org.subscription_tier}'")
    
    db.session.commit()
    print("✅ Organization migration completed!")

def migrate_existing_subscriptions():
    """Migrate existing subscriptions to use tier IDs"""
    if not current_app:
        raise RuntimeError("migrate_existing_subscriptions() must be called within Flask application context")
    
    print("=== Migrating Subscriptions to Tier IDs ===")
    
    subscriptions = Subscription.query.all()
    
    for sub in subscriptions:
        if sub.tier and not sub.tier_id:
            # Find matching tier by key
            tier = SubscriptionTier.query.filter_by(key=sub.tier).first()
            if tier:
                sub.tier_id = tier.id
                print(f"✅ Migrated subscription {sub.id} to tier ID {tier.id} ({tier.key})")
            else:
                print(f"⚠️  No tier found for subscription {sub.id} with tier '{sub.tier}'")
    
    db.session.commit()
    print("✅ Subscription migration completed!")

def seed_subscriptions():
    """Main subscription seeder function - creates proper tier structure"""
    if not current_app:
        raise RuntimeError("seed_subscriptions() must be called within Flask application context")
    
    print("=== Seeding Subscription Foundation ===")
    
    # Step 1: Create tier records from JSON
    seed_subscription_tiers()
    
    # Step 2: Migrate existing organizations
    migrate_existing_organizations()
    
    # Step 3: Migrate existing subscriptions
    migrate_existing_subscriptions()
    
    # Step 4: Ensure test organization has exempt subscription
    exempt_tier = SubscriptionTier.query.filter_by(key='exempt').first()
    if exempt_tier:
        org = Organization.query.first()
        if org and not org.subscription_tier_id:
            org.subscription_tier_id = exempt_tier.id
            db.session.commit()
            print(f"✅ Assigned exempt tier to test organization")
    
    print("✅ Subscription foundation seeding completed!")
    print("   - Tier records created with proper IDs")
    print("   - Organizations migrated to tier IDs")
    print("   - Subscriptions migrated to tier IDs")
