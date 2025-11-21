
#!/usr/bin/env python3
"""
Realistic Load Test Runner

This tests the application as-is to find actual bottlenecks and weak spots.
No modifications to the app - pure stress testing.
"""
import os
import sys
import subprocess
import time

def run_realistic_load_test():
    """Run realistic load test that reveals actual app weaknesses"""
    
    # No environment changes - test the app as it is
    env = os.environ.copy()
    
    print("🎯 Starting REALISTIC load test...")
    print("📊 This will reveal your app's actual bottlenecks")
    print("⚡ Rate limiting will cause failures - that's the point!")
    print("💡 Dashboard: http://0.0.0.0:8091 (switch webview to port 3002)")
    print()
    
    # Create test users first
    print("👥 Creating test users...")
    create_users_cmd = [
        'python', '-c', '''
from app import create_app
from app.extensions import db
from app.models import User, Organization, SubscriptionTier
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    # Create exempt tier for testing
    exempt_tier = SubscriptionTier.query.filter_by(name='Exempt Plan').first()
    if not exempt_tier:
        exempt_tier = SubscriptionTier(
            name='Exempt Plan',
            stripe_tier_id=None,
            whop_tier_id=None,
            user_limit=-1,
            is_active=True,
            requires_stripe_billing=False,
            requires_whop_billing=False,
            has_valid_integration=True
        )
        db.session.add(exempt_tier)
        db.session.flush()
    
    # Create test organization with exempt tier
    test_org = Organization.query.filter_by(name='Test Organization').first()
    if not test_org:
        test_org = Organization(
            name='Test Organization',
            tier_id=exempt_tier.id,
            billing_status='active'
        )
        db.session.add(test_org)
        db.session.flush()
    else:
        test_org.tier_id = exempt_tier.id
        test_org.billing_status = 'active'
    
    # Create test user
    test_user = User.query.filter_by(username='test@example.com').first()
    if not test_user:
        test_user = User(
            username='test@example.com',
            email='test@example.com',
            first_name='Test',
            last_name='User',
            password_hash=generate_password_hash('testpassword123'),
            is_active=True,
            user_type='customer',
            organization_id=test_org.id
        )
        db.session.add(test_user)
    else:
        test_user.organization_id = test_org.id
        test_user.is_active = True
    
    # Create developer user
    dev_user = User.query.filter_by(username='dev').first()
    if not dev_user:
        dev_user = User(
            username='dev',
            email='dev@batchtrack.com',
            first_name='Developer',
            last_name='User',
            password_hash=generate_password_hash('devpassword123'),
            is_active=True,
            user_type='developer',
            organization_id=None
        )
        db.session.add(dev_user)
    
    db.session.commit()
    print('✅ Test users ready for realistic load testing')
'''
    ]
    
    result = subprocess.run(create_users_cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ User creation failed: {result.stderr}")
        return False
    
    print(result.stdout)
    
    # Run the realistic load test
    print("🔥 Starting realistic load test...")
    print("💭 Expect failures - they show where your app breaks!")
    print()
    print("📈 Recommended test phases:")
    print("   1. Start with 10 users, 2/sec spawn rate")
    print("   2. Gradually increase to find breaking point")
    print("   3. Watch for rate limit errors (429) vs real errors (500)")
    print("   4. Monitor response times and failure patterns")
    print()
    
    load_test_cmd = [
        'locust', 
        '-f', 'loadtests/locustfile.py',
        '--host=http://0.0.0.0:5000',
        '--web-host=0.0.0.0',
        '--web-port=8091'
    ]
    
    result = subprocess.run(load_test_cmd, env=env)
    return result.returncode == 0

if __name__ == '__main__':
    success = run_realistic_load_test()
    sys.exit(0 if success else 1)
