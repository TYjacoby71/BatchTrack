
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

def seed_subscription_for_organization_one():
    """Create exempt subscription for organization 1"""
    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_subscription_for_organization_one() must be called within Flask application context")
    
    # Check if org 1 exists and create subscription if missing
    org = Organization.query.get(1)
    if org:
        sub = Subscription.query.filter_by(organization_id=1).first()
        if not sub:
            print('Creating exempt subscription for organization 1')
            sub = Subscription(
                organization_id=1,
                tier='exempt',
                status='active',
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                notes='Reserved organization for owner and testing'
            )
            db.session.add(sub)
            db.session.commit()
            print('✅ Created subscription successfully')
        else:
            print(f'ℹ️  Subscription already exists: {sub.tier}')
            if sub.tier != 'exempt':
                sub.tier = 'exempt'
                sub.status = 'active'
                db.session.commit()
                print('✅ Updated to exempt tier')
    else:
        print('❌ Organization 1 not found')

def seed_subscriptions():
    """Main subscription seeder function"""
    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_subscriptions() must be called within Flask application context")
    
    print("=== Seeding Subscription Data ===")
    
    # Seed exempt subscription for organization 1
    seed_subscription_for_organization_one()
    
    print("✅ Subscription seeding completed!")
