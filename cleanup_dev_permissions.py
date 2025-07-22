
#!/usr/bin/env python3
"""Remove developer/admin permissions from organization permission system"""

from app import create_app
from app.models.permission import Permission
from app.extensions import db

def cleanup_developer_permissions():
    """Remove developer/admin permissions from organization permission table"""
    
    # List of permission names that should only exist in developer_permission table
    dev_admin_permissions = [
        # Developer permissions
        'dev.dashboard',
        'dev.debug_mode', 
        'dev.access_logs',
        'dev.run_migrations',
        'dev.seed_data',
        'dev.system_settings',
        
        # System permissions
        'system.admin',
        'system.view_all_organizations',
        'system.create_organizations', 
        'system.delete_organizations',
        'system.modify_subscriptions',
        'system.access_billing',
        'system.manage_users',
        
        # Admin permissions that shouldn't be in org system
        'admin.user_management',
        'admin.audit_logs',
        'admin.system_health',
        'admin.backup_restore'
    ]
    
    removed_count = 0
    for perm_name in dev_admin_permissions:
        permission = Permission.query.filter_by(name=perm_name).first()
        if permission:
            print(f"Removing {perm_name} from organization permissions")
            db.session.delete(permission)
            removed_count += 1
    
    # Also remove any permissions with dev.*, system.*, or admin.* patterns
    all_permissions = Permission.query.all()
    for perm in all_permissions:
        if (perm.name.startswith('dev.') or 
            perm.name.startswith('system.') or 
            perm.name.startswith('admin.')):
            print(f"Removing pattern-matched {perm.name} from organization permissions")
            db.session.delete(perm)
            removed_count += 1
    
    db.session.commit()
    print(f"✅ Removed {removed_count} developer/admin permissions from organization system")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        print("Cleaning up developer permissions from organization system...")
        cleanup_developer_permissions()
        print("✅ Cleanup complete!")
