from ..models import User, Organization, Role
from ..extensions import db
from werkzeug.security import generate_password_hash

def seed_users():
    """Seed default users into the database"""

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

    # Assign all users proper roles based on their user types
    all_users = User.query.all()
    for user in all_users:
        if user.user_type == 'developer' and developer_role:
            user.role_id = developer_role.id
        elif user.user_type == 'organization_owner' and org_owner_role:
            user.role_id = org_owner_role.id
        elif user.user_type == 'team_member' and manager_role:
            user.role_id = manager_role.id
        print(f"✅ Assigned role to existing user: {user.username} -> {user.user_type}")
    
    db.session.commit()

    # Create developer user if it doesn't exist
    if not User.query.filter_by(username='dev').first():
        developer_user = User(
            username='dev',
            password_hash=generate_password_hash('dev123'),
            role_id=developer_role.id,
            first_name='System',
            last_name='Developer',
            email='dev@batchtrack.com',
            phone='000-000-0000',
            organization_id=org.id,
            is_owner=False,
            user_type='developer',  # Add user_type
            is_active=True
        )
        db.session.add(developer_user)
        print(f"✅ Created developer user: dev/dev123 (org_id: {org.id})")
    else:
        # Update existing developer user with missing fields
        dev_user = User.query.filter_by(username='dev').first()
        if not dev_user.user_type:
            dev_user.user_type = 'developer'
            dev_user.role_id = developer_role.id
        dev_user.is_active = True  # Ensure user is active
        print(f"✅ Updated developer user with user_type and role")

    # Create organization owner (admin) user if it doesn't exist
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin'),
            role_id=org_owner_role.id,
            first_name='Jacob',
            last_name='Boulette',
            email='jacobboulette@outlook.com',
            phone='775-934-5968',
            organization_id=org.id,
            is_owner=True,
            user_type='organization_owner',  # Add user_type
            is_active=True
        )
        db.session.add(admin_user)
        print(f"✅ Created organization owner user: admin/admin (org_id: {org.id})")
    else:
        # Update existing admin user with missing fields
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user.user_type:
            admin_user.user_type = 'organization_owner'
            admin_user.role_id = org_owner_role.id
            admin_user.is_owner = True
        admin_user.is_active = True  # Ensure user is active
        print(f"✅ Updated admin user with user_type and role")

    # Create a sample manager user if it doesn't exist
    if not User.query.filter_by(username='manager').first() and manager_role:
        manager_user = User(
            username='manager',
            password_hash=generate_password_hash('manager123'),
            role_id=manager_role.id,
            first_name='Sample',
            last_name='Manager',
            email='manager@example.com',
            phone='555-0124',
            organization_id=org.id,
            is_owner=False,
            user_type='team_member',  # Add user_type
            is_active=True
        )
        db.session.add(manager_user)
        print(f"✅ Created sample manager user: manager/manager123 (org_id: {org.id})")
    else:
        if User.query.filter_by(username='manager').first():
            manager_user = User.query.filter_by(username='manager').first()
            if not manager_user.user_type:
                manager_user.user_type = 'team_member'
                manager_user.role_id = manager_role.id if manager_role else manager_user.role_id
            manager_user.is_active = True  # Ensure user is active
            print(f"✅ Updated manager user with user_type")

    # Create sample operator user if it doesn't exist
    if not User.query.filter_by(username='operator').first() and operator_role:
        operator_user = User(
            username='operator',
            password_hash=generate_password_hash('operator123'),
            role_id=operator_role.id,
            first_name='Sample',
            last_name='Operator',
            email='operator@example.com',
            phone='555-0125',
            organization_id=org.id,
            is_owner=False,
            user_type='team_member',  # Add user_type
            is_active=True
        )
        db.session.add(operator_user)
        print(f"✅ Created sample operator user: operator/operator123 (org_id: {org.id})")
    else:
        if User.query.filter_by(username='operator').first():
            operator_user = User.query.filter_by(username='operator').first()
            if not operator_user.user_type:
                operator_user.user_type = 'team_member'
                operator_user.role_id = operator_role.id if operator_role else operator_user.role_id
            operator_user.is_active = True  # Ensure user is active
            print(f"✅ Updated operator user with user_type")

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
            elif user.is_owner:
                user.user_type = 'organization_owner'
            else:
                user.user_type = 'team_member'
            updated = True

        # Set role_id if missing
        if not user.role_id:
            if user.user_type == 'developer' and developer_role:
                user.role_id = developer_role.id
            elif user.user_type == 'organization_owner' and org_owner_role:
                user.role_id = org_owner_role.id
            elif user.user_type == 'team_member':
                # Assign manager role by default for team members
                user.role_id = manager_role.id if manager_role else org_owner_role.id
            updated = True

        # Ensure is_active is set
        if not hasattr(user, 'is_active') or user.is_active is None:
            user.is_active = True
            updated = True

        if updated:
            print(f"✅ Updated user {user.username} with user_type: {user.user_type}")

    db.session.commit()
    print("✅ Existing users updated with database roles and user_type")