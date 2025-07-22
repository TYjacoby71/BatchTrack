from ..models import User, Organization, Role
from ..extensions import db
from werkzeug.security import generate_password_hash

def seed_users():
    """Seed default users into the database"""
    from flask import current_app
    
    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_users() must be called within Flask application context")

    # Import Role at top of function to avoid scope issues
    from app.models.role import Role
    from ..models.developer_role import DeveloperRole
    from ..models.user_role_assignment import UserRoleAssignment

    # Get or create default organization
    org = Organization.query.first()
    if not org:
        org = Organization(
            name="Jacob Boulette's Organization",
            subscription_tier='team'  # Changed from 'free' to 'team' for better features
        )
        db.session.add(org)
        db.session.commit()  # Commit to ensure we have a valid ID
        print(f"✅ Created organization: {org.name} (ID: {org.id})")
    else:
        print(f"ℹ️  Using existing organization: {org.name} (ID: {org.id})")

    # Get roles from database - these should exist from role_permission_seeder
    developer_role = Role.query.filter_by(name='developer').first()
    org_owner_role = Role.query.filter_by(name='organization_owner').first()
    manager_role = Role.query.filter_by(name='manager').first()
    operator_role = Role.query.filter_by(name='operator').first()

    if not developer_role or not org_owner_role:
        print("❌ Required roles not found. Please run 'flask seed-roles-permissions' first.")
        return

    # Get organization owner system role
    system_org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()

    # Assign all users proper roles based on their user types (excluding developers)
    all_users = User.query.filter(User.user_type != 'developer').all()
    for user in all_users:
        if user.user_type == 'organization_owner':
            if system_org_owner_role:
                user.assign_role(system_org_owner_role)
                print(f"✅ Assigned system organization owner role to: {user.username}")
            elif org_owner_role:
                user.assign_role(org_owner_role)
                print(f"✅ Assigned legacy organization owner role to: {user.username}")
        elif user.user_type == 'team_member' and manager_role:
            user.assign_role(manager_role)
            print(f"✅ Assigned role to existing user: {user.username} -> {user.user_type}")
    
    # Also handle users with is_organization_owner flag (for backward compatibility)
    org_owner_flagged_users = User.query.filter_by(is_organization_owner=True).all()
    fixed_count = 0
    
    for user in org_owner_flagged_users:
        if user.user_type != 'developer':  # Skip developers
            # Check if user already has organization owner role
            has_org_owner_role = any(
                assignment.role and assignment.role.name == 'organization_owner' 
                for assignment in user.role_assignments if assignment.is_active
            )
            
            if not has_org_owner_role:
                if system_org_owner_role:
                    user.assign_role(system_org_owner_role)
                    fixed_count += 1
                    print(f"✅ Fixed organization owner role for flagged user: {user.username}")
                elif org_owner_role:
                    user.assign_role(org_owner_role)
                    fixed_count += 1
                    print(f"✅ Fixed legacy organization owner role for flagged user: {user.username}")
    
    if fixed_count > 0:
        print(f"✅ Fixed {fixed_count} organization owner users with missing roles")

    # Ensure all developer users have no organization association
    developer_users = User.query.filter(User.user_type == 'developer').all()
    for dev_user in developer_users:
        if dev_user.organization_id is not None:
            print(f"⚠️  Removing organization association from developer: {dev_user.username}")
            dev_user.organization_id = None

    db.session.commit()

    # Create developer user if it doesn't exist
    if not User.query.filter_by(username='dev').first():
        developer_user = User(
            username='dev',
            password_hash=generate_password_hash('dev123'),
            first_name='System',
            last_name='Developer',
            email='dev@batchtrack.com',
            phone='000-000-0000',
            organization_id=None,  # Developers don't belong to customer organizations
            user_type='developer',
            is_active=True
        )
        db.session.add(developer_user)
        db.session.flush()  # Get the user ID

        # Assign system_admin developer role
        system_admin_role = DeveloperRole.query.filter_by(name='system_admin').first()
        if system_admin_role:
            assignment = UserRoleAssignment(
                user_id=developer_user.id,
                developer_role_id=system_admin_role.id,
                organization_id=None,
                is_active=True
            )
            db.session.add(assignment)
            print(f"✅ Assigned system_admin role to dev user")

        print(f"✅ Created developer user: dev/dev123 (no organization)")
    else:
        # Update existing developer user
        dev_user = User.query.filter_by(username='dev').first()
        dev_user.user_type = 'developer'
        dev_user.organization_id = None  # Remove from customer organization
        dev_user.is_active = True

        # Create developer user with system_admin role
        print("✅ Assigned system_admin role to existing dev user")
        dev_user = User.query.filter_by(username='dev').first()
        if dev_user:
            dev_user.user_type = 'developer'
            print("✅ Updated developer user with user_type: developer")

            # Get system_admin developer role
            system_admin_role = DeveloperRole.query.filter_by(name='system_admin').first()
            if system_admin_role:
                # Check if assignment already exists
                existing_assignment = UserRoleAssignment.query.filter_by(
                    user_id=dev_user.id,
                    developer_role_id=system_admin_role.id
                ).first()

                if not existing_assignment:
                    assignment = UserRoleAssignment(
                        user_id=dev_user.id,
                        role_id=None,  # Explicitly set to None for developer roles
                        developer_role_id=system_admin_role.id,
                        organization_id=None,
                        is_active=True
                    )
                    db.session.add(assignment)

            # Commit developer user changes before proceeding
            db.session.commit()


        print(f"✅ Updated developer user with user_type: developer")

    # Create organization owner (admin) user if it doesn't exist
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin'),
            first_name='Jacob',
            last_name='Boulette',
            email='jacobboulette@outlook.com',
            phone='775-934-5968',
            organization_id=org.id,
            user_type='customer',  # Everyone is customer type now
            is_organization_owner=True,  # This flag determines ownership
            is_active=True
        )
        db.session.add(admin_user)
        print(f"✅ Created organization owner user: admin/admin (org_id: {org.id})")
    else:
        # Update existing admin user with missing fields
        admin_user = User.query.filter_by(username='admin').first()
        admin_user.user_type = 'customer'  # Update to customer type
        admin_user.is_organization_owner = True  # Set the ownership flag
        admin_user.is_active = True  # Ensure user is active
        print(f"✅ Updated admin user with user_type=customer and is_organization_owner=True")

    # Create a sample manager user if it doesn't exist
    if not User.query.filter_by(username='manager').first() and manager_role:
        manager_user = User(
            username='manager',
            password_hash=generate_password_hash('manager123'),
            first_name='Sample',
            last_name='Manager',
            email='manager@example.com',
            phone='555-0124',
            organization_id=org.id,
            user_type='customer',  # Everyone is customer type now
            is_organization_owner=False,  # Not an organization owner
            is_active=True
        )
        db.session.add(manager_user)
        print(f"✅ Created sample manager user: manager/manager123 (org_id: {org.id})")
    else:
        if User.query.filter_by(username='manager').first():
            manager_user = User.query.filter_by(username='manager').first()
            manager_user.user_type = 'customer'  # Update to customer type
            manager_user.is_organization_owner = False  # Not an owner
            manager_user.is_active = True  # Ensure user is active
            print(f"✅ Updated manager user with user_type=customer")

    # Create sample operator user if it doesn't exist
    if not User.query.filter_by(username='operator').first() and operator_role:
        operator_user = User(
            username='operator',
            password_hash=generate_password_hash('operator123'),
            first_name='Sample',
            last_name='Operator',
            email='operator@example.com',
            phone='555-0125',
            organization_id=org.id,
            user_type='customer',  # Everyone is customer type now
            is_organization_owner=False,  # Not an organization owner
            is_active=True
        )
        db.session.add(operator_user)
        print(f"✅ Created sample operator user: operator/operator123 (org_id: {org.id})")
    else:
        if User.query.filter_by(username='operator').first():
            operator_user = User.query.filter_by(username='operator').first()
            operator_user.user_type = 'customer'  # Update to customer type
            operator_user.is_organization_owner = False  # Not an owner
            operator_user.is_active = True  # Ensure user is active
            print(f"✅ Updated operator user with user_type=customer")

    db.session.commit()
    print("✅ User seeding completed")

def update_existing_users_with_roles():
    """Update existing users to have database role assignments and user_type"""
    users = User.query.all()

    # Get roles
    developer_role = Role.query.filter_by(name='developer').first()
    org_owner_role = Role.query.filter_by(name='organization_owner').first()
    manager_role = Role.query.filter_by(name='manager').first()
    operator_role = Role.query.filter_by(name='operator').first()

    for user in users:
        updated = False

        # Set user_type if missing
        if not hasattr(user, 'user_type') or not user.user_type:
            if user.username == 'dev':
                user.user_type = 'developer'
            else:
                user.user_type = 'customer'  # Everyone else is customer type
            updated = True
        
        # Set is_organization_owner flag if missing
        if not hasattr(user, 'is_organization_owner') or user.is_organization_owner is None:
            if user.username == 'admin':
                user.is_organization_owner = True
            elif user.user_type != 'developer':
                user.is_organization_owner = False
            updated = True

        # Ensure developers have no organization association
        if user.user_type == 'developer':
            if user.organization_id is not None:
                print(f"⚠️  Removing organization association from developer: {user.username}")
                user.organization_id = None
                updated = True
            # Skip role assignment for developers
        else:
            # Assign roles using the new role assignment system
            if user.user_type == 'organization_owner' and org_owner_role:
                user.assign_role(org_owner_role)
                print(f"✅ Assigned organization owner role to {user.username}")
            elif user.user_type == 'team_member' and manager_role:
                user.assign_role(manager_role)
                print(f"✅ Assigned manager role to {user.username}")

        # Ensure is_active is set
        if not hasattr(user, 'is_active') or user.is_active is None:
            user.is_active = True
            updated = True

        if updated:
            print(f"✅ Updated user {user.username} with user_type: {user.user_type}")

    db.session.commit()
    print("✅ Existing users updated with database roles and user_type")