
"""
Test User Generator for Load Testing

Creates multiple unique test users to avoid single session conflicts during load testing.
"""

import sys
import os

# Add the parent directory to Python path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User, Organization, SubscriptionTier
from werkzeug.security import generate_password_hash

def create_load_test_users(count=100, base_username="loadtest_user", password="loadtest123"):
    """
    Create multiple test users for load testing to avoid session conflicts.
    
    Args:
        count (int): Number of users to create
        base_username (str): Base username pattern
        password (str): Password for all test users
    """
    
    app = create_app()
    
    with app.app_context():
        # Get or create a test organization
        org = Organization.query.filter_by(name='Load Test Organization').first()
        if not org:
            # Get exempt tier for test org
            exempt_tier = SubscriptionTier.query.filter_by(name='Exempt Plan').first()
            if not exempt_tier:
                print("❌ No Exempt Plan found! Run subscription seeder first.")
                return []
            
            org = Organization(
                name='Load Test Organization',
                contact_email='loadtest@example.com',
                subscription_tier_id=exempt_tier.id
            )
            db.session.add(org)
            db.session.flush()
            print(f"✅ Created Load Test Organization")
        
        created_users = []
        existing_count = 0
        
        for i in range(1, count + 1):
            username = f"{base_username}{i}"
            email = f"{username}@example.com"
            
            # Check if user already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                existing_count += 1
                created_users.append({
                    'username': username,
                    'password': password,
                    'email': email,
                    'status': 'existing'
                })
                continue
            
            # Create new user
            user = User(
                username=username,
                email=email,
                first_name=f"Load Test",
                last_name=f"User {i}",
                organization_id=org.id,
                user_type='customer',
                is_active=True,
                email_verified=True  # Pre-verify for testing
            )
            user.set_password(password)
            
            db.session.add(user)
            created_users.append({
                'username': username,
                'password': password,
                'email': email,
                'status': 'created'
            })
        
        try:
            db.session.commit()
            new_users = len([u for u in created_users if u['status'] == 'created'])
            print(f"✅ Load test users ready: {new_users} created, {existing_count} existing")
            print(f"   Total available: {len(created_users)} users")
            print(f"   Username pattern: {base_username}1, {base_username}2, ..., {base_username}{count}")
            print(f"   Password: {password}")
            
            return created_users
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating users: {e}")
            return []

def cleanup_load_test_users(base_username="loadtest_user"):
    """
    Clean up load test users and organization.
    """
    app = create_app()
    
    with app.app_context():
        # Delete users with the pattern
        users_deleted = User.query.filter(User.username.like(f"{base_username}%")).delete(synchronize_session=False)
        
        # Delete test organization
        org = Organization.query.filter_by(name='Load Test Organization').first()
        org_deleted = 0
        if org:
            db.session.delete(org)
            org_deleted = 1
        
        db.session.commit()
        print(f"✅ Cleanup complete: {users_deleted} users deleted, {org_deleted} organization deleted")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Manage load test users')
    parser.add_argument('action', choices=['create', 'cleanup'], help='Action to perform')
    parser.add_argument('--count', type=int, default=100, help='Number of users to create (default: 100)')
    parser.add_argument('--username', default='loadtest_user', help='Base username pattern (default: loadtest_user)')
    parser.add_argument('--password', default='loadtest123', help='Password for test users (default: loadtest123)')
    
    args = parser.parse_args()
    
    if args.action == 'create':
        users = create_load_test_users(args.count, args.username, args.password)
        if users:
            print(f"\n📋 Sample credentials:")
            for i in range(min(5, len(users))):
                user = users[i]
                print(f"   {user['username']} / {user['password']}")
            if len(users) > 5:
                print(f"   ... and {len(users) - 5} more")
    
    elif args.action == 'cleanup':
        cleanup_load_test_users(args.username)
