
#!/usr/bin/env python3

from app.models import Permission, Role, User
from app.extensions import db
from app import create_app

def fix_organization_owner_permissions():
    """Fix organization owner role to have all organization permissions"""
    app = create_app()
    
    with app.app_context():
        print("=== Fixing Organization Owner Role Permissions ===")
        
        # Find the organization owner role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        
        if not org_owner_role:
            print("❌ Organization owner role not found!")
            return
        
        print(f"Found organization owner role with {len(org_owner_role.permissions)} permissions")
        
        # Get all organization permissions
        all_org_permissions = Permission.query.filter_by(is_active=True).all()
        print(f"Total organization permissions available: {len(all_org_permissions)}")
        
        # Clear existing permissions and add all
        org_owner_role.permissions.clear()
        org_owner_role.permissions = all_org_permissions
        
        db.session.commit()
        
        print(f"✅ Updated organization owner role with all {len(all_org_permissions)} permissions")
        
        # Verify the update
        updated_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        print(f"✅ Verification: Role now has {len(updated_role.permissions)} permissions")
        
        print("=== Fix Complete ===")

if __name__ == "__main__":
    fix_organization_owner_permissions()
