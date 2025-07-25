
#!/usr/bin/env python3
"""Seed subscription tiers and data"""

import json
import os
from flask import current_app
from ..models import db, Organization, Subscription
from datetime import datetime

def load_subscription_tiers():
    """Load subscription tiers from JSON file"""
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'subscription_tiers.json')
    with open(json_path, 'r') as f:
        return json.load(f)

def seed_exempt_subscription_tier():
    """Create the exempt subscription tier in the database if it doesn't exist"""
    if not current_app:
        raise RuntimeError("seed_exempt_subscription_tier() must be called within Flask application context")
    
    # Check if we already have subscription tiers seeded by checking for exempt tier data
    print("=== Creating Exempt Subscription Tier ===")
    
    # Load subscription tiers from JSON
    tiers_data = load_subscription_tiers()
    exempt_tier_data = tiers_data.get('exempt')
    
    if not exempt_tier_data:
        print("❌ Exempt tier not found in subscription_tiers.json")
        return
    
    print("✅ Exempt tier configuration loaded from JSON")
    print(f"   - Name: {exempt_tier_data.get('name')}")
    print(f"   - User Limit: {exempt_tier_data.get('user_limit')}")
    print(f"   - Permissions: {len(exempt_tier_data.get('permissions', []))} permissions")
    
    # The exempt tier is now ready for assignment to organizations
    print("✅ Exempt subscription tier is available for assignment")

def seed_subscription_for_test_organization():
    """Create exempt subscription for the test organization"""
    if not current_app:
        raise RuntimeError("seed_subscription_for_test_organization() must be called within Flask application context")
    
    print("=== Assigning Exempt Subscription to Test Organization ===")
    
    # Get or create the test organization (this should exist from user seeder)
    org = Organization.query.first()
    if not org:
        # Create the organization if it doesn't exist
        org = Organization(
            name="Jacob Boulette's Organization",
            subscription_tier='exempt'  # Set to exempt tier
        )
        db.session.add(org)
        db.session.commit()
        print(f"✅ Created test organization: {org.name} (ID: {org.id})")
    else:
        # Update existing organization to exempt tier
        org.subscription_tier = 'exempt'
        db.session.commit()
        print(f"ℹ️  Updated existing organization: {org.name} (ID: {org.id}) to exempt tier")

    # Check if subscription record exists
    sub = Subscription.query.filter_by(organization_id=org.id).first()
    if not sub:
        print(f'Creating exempt subscription for organization {org.id}')
        sub = Subscription(
            organization_id=org.id,
            tier='exempt',
            status='active',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            notes='Development/testing organization with exempt tier'
        )
        db.session.add(sub)
        db.session.commit()
        print('✅ Created exempt subscription successfully')
    else:
        print(f'ℹ️  Subscription already exists: {sub.tier}')
        if sub.tier != 'exempt':
            sub.tier = 'exempt'
            sub.status = 'active'
            sub.notes = 'Development/testing organization with exempt tier'
            db.session.commit()
            print('✅ Updated to exempt tier')

def seed_subscriptions():
    """Main subscription seeder function - creates exempt tier foundation"""
    if not current_app:
        raise RuntimeError("seed_subscriptions() must be called within Flask application context")
    
    print("=== Seeding Subscription Foundation ===")
    
    # Step 1: Ensure exempt tier is available in JSON config
    seed_exempt_subscription_tier()
    
    # Step 2: Create/update test organization with exempt subscription
    seed_subscription_for_test_organization()
    
    print("✅ Subscription foundation seeding completed!")
    print("   - Exempt tier available for assignment")
    print("   - Test organization has exempt subscription")
    print("   - Ready for user seeder to assign users")
