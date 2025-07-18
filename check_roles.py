
#!/usr/bin/env python3
"""
Check available roles and permissions for testing invite user functionality
"""

import sys
import os

# Add the app directory to the path so we can import models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def check_roles():
    """Check what roles are available in the database"""
    
    try:
        from app.models import Role, Permission
        from app.extensions import db
        from app import create_app
        
        # Create app context
        app = create_app()
        
        with app.app_context():
            print("🔍 Checking available roles and permissions...")
            print("="*60)
            
            # Get all roles
            roles = Role.query.all()
            
            if not roles:
                print("❌ No roles found in database")
                print("You may need to run the role seeder first")
                return
            
            print("Available Roles:")
            print("-" * 30)
            
            for role in roles:
                print(f"ID: {role.id}")
                print(f"Name: {role.name}")
                print(f"Description: {role.description}")
                
                # Get permissions for this role
                permissions = [p.name for p in role.permissions] if hasattr(role, 'permissions') else []
                print(f"Permissions: {len(permissions)} assigned")
                
                if permissions:
                    print("Sample permissions:", permissions[:3])
                    if len(permissions) > 3:
                        print(f"... and {len(permissions) - 3} more")
                
                print("-" * 30)
            
            # Check if developer role exists (should not be assignable)
            dev_role = Role.query.filter_by(name='developer').first()
            if dev_role:
                print(f"⚠️  Developer role found (ID: {dev_role.id}) - this should NOT be assignable to organization users")
            
            print(f"\n✅ Found {len(roles)} total roles")
            print("\nFor testing invite user, use role IDs 2-4 (avoid developer role)")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the project root directory")
    except Exception as e:
        print(f"❌ Error: {e}")

def check_organizations():
    """Check available organizations"""
    
    try:
        from app.models import Organization, User
        from app.extensions import db
        from app import create_app
        
        app = create_app()
        
        with app.app_context():
            print("\n🏢 Checking organizations...")
            print("="*60)
            
            orgs = Organization.query.all()
            
            for org in orgs:
                print(f"Organization: {org.name}")
                print(f"ID: {org.id}")
                print(f"Subscription: {org.subscription_tier}")
                print(f"Active users: {org.active_users_count}")
                print(f"Max users allowed: {org.get_max_users()}")
                print(f"Can add users: {org.can_add_users()}")
                
                # Find organization owner
                owner = User.query.filter_by(
                    organization_id=org.id, 
                    user_type='organization_owner'
                ).first()
                
                if owner:
                    print(f"Owner: {owner.username} ({owner.full_name})")
                
                print("-" * 30)
                
    except Exception as e:
        print(f"❌ Error checking organizations: {e}")

def fix_organization_limits():
    """Temporarily increase organization user limits for testing"""
    
    try:
        from app.models import Organization
        from app.extensions import db
        from app import create_app
        
        app = create_app()
        
        with app.app_context():
            print("\n🔧 Fixing organization limits for testing...")
            print("="*60)
            
            orgs = Organization.query.all()
            
            for org in orgs:
                if org.subscription_tier == 'free':
                    print(f"Upgrading {org.name} from 'free' to 'team' for testing")
                    org.subscription_tier = 'team'  # Allows up to 10 users
                    db.session.commit()
                    print(f"✅ {org.name} can now have up to {org.get_max_users()} users")
                else:
                    print(f"{org.name} already has {org.subscription_tier} subscription")
                    
    except Exception as e:
        print(f"❌ Error fixing organization limits: {e}")

if __name__ == "__main__":
    check_roles()
    check_organizations()
    
    # Optionally fix organization limits
    if len(sys.argv) > 1 and sys.argv[1] == "--fix-limits":
        fix_organization_limits()
        print("\nRe-checking organizations after limit fix:")
        check_organizations()
