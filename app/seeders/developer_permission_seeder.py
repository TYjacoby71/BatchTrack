
from ..models.developer_permission import DeveloperPermission
from ..models.developer_role import DeveloperRole
from ..extensions import db

def seed_developer_permissions():
    """Seed developer/system permissions"""
    # Import Permission model to copy all application permissions
    from ..models.permission import Permission
    
    developer_permissions = [
        # System administration
        {'name': 'system.admin', 'description': 'Full system administration', 'category': 'system'},
        {'name': 'system.view_all_organizations', 'description': 'View all organizations', 'category': 'system'},
        {'name': 'system.create_organizations', 'description': 'Create organizations', 'category': 'system'},
        {'name': 'system.delete_organizations', 'description': 'Delete organizations', 'category': 'system'},
        {'name': 'system.modify_subscriptions', 'description': 'Modify subscription tiers', 'category': 'system'},
        {'name': 'system.access_billing', 'description': 'Access all billing information', 'category': 'system'},
        {'name': 'system.manage_users', 'description': 'Manage all users across organizations', 'category': 'system'},
        
        # Developer tools
        {'name': 'dev.dashboard', 'description': 'Access developer dashboard', 'category': 'developer'},
        {'name': 'dev.debug_mode', 'description': 'Enable debug mode', 'category': 'developer'},
        {'name': 'dev.access_logs', 'description': 'Access system logs', 'category': 'developer'},
        {'name': 'dev.run_migrations', 'description': 'Run database migrations', 'category': 'developer'},
        {'name': 'dev.seed_data', 'description': 'Seed database with test data', 'category': 'developer'},
        {'name': 'dev.system_settings', 'description': 'Modify system settings', 'category': 'developer'},
        
        # Administrative functions
        {'name': 'admin.user_management', 'description': 'Advanced user management', 'category': 'admin'},
        {'name': 'admin.audit_logs', 'description': 'View audit logs', 'category': 'admin'},
        {'name': 'admin.system_health', 'description': 'View system health metrics', 'category': 'admin'},
        {'name': 'admin.backup_restore', 'description': 'Backup and restore operations', 'category': 'admin'},
    ]
    
    # Add all application permissions to developer permissions system
    app_permissions = Permission.query.all()
    for app_perm in app_permissions:
        developer_permissions.append({
            'name': f'app.{app_perm.name}',
            'description': f'[App Permission] {app_perm.description}',
            'category': 'application'
        })
    
    for perm_data in developer_permissions:
        existing = DeveloperPermission.query.filter_by(name=perm_data['name']).first()
        if not existing:
            perm = DeveloperPermission(**perm_data)
            db.session.add(perm)
    
    db.session.commit()
    print("Developer permissions seeded successfully")

def seed_developer_roles():
    """Seed developer/system roles"""
    roles_data = [
        {
            'name': 'system_admin',
            'description': 'Full system administrator with all permissions',
            'category': 'system',
            'permissions': ['system.*', 'dev.*', 'admin.*']  # All permissions
        },
        {
            'name': 'developer',
            'description': 'BatchTrack developer with development tools access',
            'category': 'developer', 
            'permissions': ['dev.*', 'system.view_all_organizations']
        },
        {
            'name': 'support_admin',
            'description': 'Customer support administrator',
            'category': 'admin',
            'permissions': ['admin.user_management', 'admin.audit_logs', 'system.view_all_organizations']
        }
    ]
    
    for role_data in roles_data:
        existing = DeveloperRole.query.filter_by(name=role_data['name']).first()
        if not existing:
            role = DeveloperRole(
                name=role_data['name'],
                description=role_data['description'],
                category=role_data['category']
            )
            db.session.add(role)
            db.session.flush()
            
            # Assign permissions (simplified - you'd want more sophisticated matching)
            all_perms = DeveloperPermission.query.all()
            for perm_pattern in role_data['permissions']:
                if perm_pattern.endswith('*'):
                    # Match by category
                    category = perm_pattern.replace('.*', '').replace('*', '')
                    matching_perms = [p for p in all_perms if p.category == category]
                    role.permissions.extend(matching_perms)
                else:
                    # Exact match
                    perm = DeveloperPermission.query.filter_by(name=perm_pattern).first()
                    if perm:
                        role.permissions.append(perm)
    
    db.session.commit()
    print("Developer roles seeded successfully")
