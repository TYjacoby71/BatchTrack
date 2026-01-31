
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
from app.models import User, Organization, SubscriptionTier, Role, Permission
from app.models.user_role_assignment import UserRoleAssignment
from app.utils.timezone_utils import TimezoneUtils
from werkzeug.security import generate_password_hash

def _ensure_org_owner_role(user, org_owner_role):
    """Ensure load test users have organization owner role + flag."""
    if not user or not org_owner_role:
        return False
    assignment = UserRoleAssignment.query.filter_by(
        user_id=user.id,
        role_id=org_owner_role.id,
        organization_id=user.organization_id,
    ).first()
    if assignment:
        assignment.is_active = True
        assignment.assigned_at = TimezoneUtils.utc_now()
    else:
        db.session.add(
            UserRoleAssignment(
                user_id=user.id,
                role_id=org_owner_role.id,
                organization_id=user.organization_id,
                assigned_at=TimezoneUtils.utc_now(),
            )
        )
    user._is_organization_owner = True
    return True


def _ensure_exempt_tier_permissions(exempt_tier):
    """Ensure the exempt tier has all active permissions."""
    if not exempt_tier:
        return False
    all_permissions = Permission.query.filter_by(is_active=True).all()
    exempt_tier.permissions = all_permissions
    return True


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
        # Resolve exempt tier (required for full permissions)
        exempt_tier = SubscriptionTier.query.filter_by(name='Exempt Plan').first()
        if not exempt_tier:
            print("❌ No Exempt Plan found! Run subscription seeder first.")
            return []
        _ensure_exempt_tier_permissions(exempt_tier)

        # Get or create a test organization
        org = Organization.query.filter_by(name='Load Test Organization').first()
        if not org:
            org = Organization(
                name='Load Test Organization',
                contact_email='loadtest@example.com',
                subscription_tier_id=exempt_tier.id,
                is_active=True,
                subscription_status='active',
                billing_status='active',
            )
            db.session.add(org)
            db.session.flush()
            print(f"✅ Created Load Test Organization")
        else:
            org.is_active = True
            if not org.subscription_status:
                org.subscription_status = 'active'
            if not org.billing_status:
                org.billing_status = 'active'
            if org.subscription_tier_id != exempt_tier.id:
                org.subscription_tier_id = exempt_tier.id
        
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        if not org_owner_role:
            print("⚠️  organization_owner role not found - run consolidated permissions seeder.")

        created_users = []
        existing_count = 0
        
        for i in range(1, count + 1):
            username = f"{base_username}{i}"
            email = f"{username}@example.com"
            
            # Check if user already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                existing_count += 1
                existing_user.is_active = True
                existing_user.email_verified = True
                if existing_user.organization_id != org.id:
                    existing_user.organization_id = org.id
                if org_owner_role and existing_user.id:
                    _ensure_org_owner_role(existing_user, org_owner_role)
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
            db.session.flush()
            if org_owner_role and user.id:
                _ensure_org_owner_role(user, org_owner_role)
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
