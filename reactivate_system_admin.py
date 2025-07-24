
#!/usr/bin/env python3
"""Reactivate the system admin permission"""

from app import create_app
from app.models import DeveloperPermission
from app.extensions import db

def reactivate_system_admin():
    """Reactivate the dev.system_admin permission"""
    app = create_app()
    
    with app.app_context():
        print("=== Reactivating System Admin Permission ===")
        
        # Find the system admin permission
        system_admin_perm = DeveloperPermission.query.filter_by(name='dev.system_admin').first()
        
        if not system_admin_perm:
            print("❌ System admin permission not found!")
            return False
        
        if system_admin_perm.is_active:
            print("✅ System admin permission is already active")
            return True
        
        # Reactivate the permission
        system_admin_perm.is_active = True
        db.session.commit()
        
        print("✅ System admin permission reactivated successfully!")
        print(f"Permission: {system_admin_perm.name}")
        print(f"Description: {system_admin_perm.description}")
        print(f"Active: {system_admin_perm.is_active}")
        
        return True

if __name__ == "__main__":
    success = reactivate_system_admin()
    if success:
        print("\n🎉 You should now be able to access the permissions page again!")
    else:
        print("\n❌ Failed to reactivate system admin permission")
