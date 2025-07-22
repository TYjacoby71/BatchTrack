
#!/usr/bin/env python3
"""Assign system_admin developer role to the dev user"""

from app import create_app
from app.models.models import User
from app.models.developer_role import DeveloperRole
from app.models.user_role_assignment import UserRoleAssignment
from app.extensions import db

def assign_system_admin_to_dev():
    """Assign system_admin role to dev user"""
    
    # Get the dev user
    dev_user = User.query.filter_by(username='dev', user_type='developer').first()
    if not dev_user:
        print("❌ Dev user not found")
        return
    
    # Get the system_admin role
    system_admin_role = DeveloperRole.query.filter_by(name='system_admin').first()
    if not system_admin_role:
        print("❌ system_admin role not found in developer_role table")
        return
    
    # Check if user already has this role assignment
    existing = UserRoleAssignment.query.filter_by(
        user_id=dev_user.id,
        developer_role_id=system_admin_role.id,
        is_active=True
    ).first()
    
    if existing:
        print(f"✓ Dev user already has system_admin role")
        return
    
    # Deactivate any existing developer role assignments for this user
    existing_assignments = UserRoleAssignment.query.filter_by(
        user_id=dev_user.id,
        is_active=True
    ).filter(UserRoleAssignment.developer_role_id.isnot(None)).all()
    
    for assignment in existing_assignments:
        assignment.is_active = False
        print(f"⚠️  Deactivated previous role: {assignment.developer_role.name}")
    
    # Create new system_admin role assignment
    assignment = UserRoleAssignment(
        user_id=dev_user.id,
        developer_role_id=system_admin_role.id,
        organization_id=None,  # Developers don't belong to organizations
        is_active=True
    )
    db.session.add(assignment)
    db.session.commit()
    
    print(f"✅ Assigned system_admin role to dev user: {dev_user.username}")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        print("Assigning system_admin role to dev user...")
        assign_system_admin_to_dev()
        print("✅ Assignment complete!")
