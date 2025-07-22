
#!/usr/bin/env python3

from app import create_app
from app.extensions import db
from app.models import User, Organization

app = create_app()

with app.app_context():
    print("=== Checking Admin User Status ===")
    
    # Find admin user
    admin_user = User.query.filter_by(username='admin').first()
    
    if not admin_user:
        print("❌ No user with username 'admin' found")
        # Show all users
        users = User.query.all()
        print("\nAvailable users:")
        for user in users:
            print(f"  - {user.username} (type: {user.user_type}, org_id: {user.organization_id})")
    else:
        print(f"✅ Found admin user: {admin_user.username}")
        print(f"   User Type: {admin_user.user_type}")
        print(f"   Organization ID: {admin_user.organization_id}")
        print(f"   Is Active: {admin_user.is_active}")
        
        if admin_user.organization:
            print(f"   Organization Name: {admin_user.organization.name}")
            print(f"   Organization Tier: {admin_user.organization.subscription_tier}")
            print(f"   Effective Tier: {admin_user.organization.effective_subscription_tier}")
        
        # Check permissions
        has_manage_org = admin_user.has_permission('manage_organization')
        print(f"   Has 'manage_organization' permission: {has_manage_org}")
        
        # Fix if needed
        needs_fix = False
        
        if admin_user.user_type != 'organization_owner':
            print(f"\n🔧 Fixing user_type from '{admin_user.user_type}' to 'organization_owner'")
            admin_user.user_type = 'organization_owner'
            needs_fix = True
        
        if admin_user.organization and admin_user.organization.subscription_tier != 'exempt':
            print(f"\n🔧 Fixing organization tier from '{admin_user.organization.subscription_tier}' to 'exempt'")
            admin_user.organization.subscription_tier = 'exempt'
            needs_fix = True
            
        if not admin_user.is_active:
            print(f"\n🔧 Activating user")
            admin_user.is_active = True
            needs_fix = True
        
        if needs_fix:
            db.session.commit()
            print("\n✅ Admin user fixed! Try accessing /organization/dashboard again")
        else:
            print("\n✅ Admin user is properly configured")
            print("\nIf you're still having issues, the problem might be:")
            print("1. JavaScript errors preventing proper loading")
            print("2. Session/authentication issues")
            print("3. Try logging out and back in")
