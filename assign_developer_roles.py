
#!/usr/bin/env python3
"""Assign developer roles to existing developer users"""

from app import create_app
from app.models.models import User
from app.models.developer_role import DeveloperRole
from app.models.user_role_assignment import UserRoleAssignment
from app.extensions import db

def assign_developer_roles():
    """Assign appropriate developer roles to developer users"""
    
    # Get all developer users
    developer_users = User.query.filter_by(user_type='developer').all()
    
    # Get the default developer role
    developer_role = DeveloperRole.query.filter_by(name='developer').first()
    if not developer_role:
        print("❌ No 'developer' role found in developer_role table")
        return
    
    for user in developer_users:
        # Check if user already has a developer role assignment
        existing = UserRoleAssignment.query.filter_by(
            user_id=user.id,
            developer_role_id=developer_role.id,
            is_active=True
        ).first()
        
        if not existing:
            # Create developer role assignment
            assignment = UserRoleAssignment(
                user_id=user.id,
                developer_role_id=developer_role.id,
                organization_id=None,  # Developers don't belong to organizations
                is_active=True
            )
            db.session.add(assignment)
            print(f"✅ Assigned 'developer' role to user: {user.username}")
        else:
            print(f"✓ User {user.username} already has developer role")
    
    db.session.commit()
    print("✅ Developer role assignments complete!")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        print("Assigning developer roles to developer users...")
        assign_developer_roles()
        print("✅ Assignment complete!")
