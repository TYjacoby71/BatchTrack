
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
            subscription_tier='free'
        )
        db.session.add(org)
        db.session.flush()  # Get the ID
    
    # Get roles from database - these should exist from role_permission_seeder
    developer_role = Role.query.filter_by(name='developer').first()
    org_owner_role = Role.query.filter_by(name='organization_owner').first()
    manager_role = Role.query.filter_by(name='manager').first()
    operator_role = Role.query.filter_by(name='operator').first()
    
    if not developer_role or not org_owner_role:
        print("❌ Required roles not found. Please run 'flask seed-roles-permissions' first.")
        return
    
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
            is_owner=False
        )
        db.session.add(developer_user)
        print("✅ Created developer user: dev/dev123")
    else:
        print("ℹ️  Developer user already exists")
    
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
            is_owner=True
        )
        db.session.add(admin_user)
        print("✅ Created organization owner user: admin/admin")
    else:
        print("ℹ️  Admin user already exists")
    
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
            is_owner=False
        )
        db.session.add(manager_user)
        print("✅ Created sample manager user: manager/manager123")
    else:
        print("ℹ️  Sample manager user already exists")
    
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
            is_owner=False
        )
        db.session.add(operator_user)
        print("✅ Created sample operator user: operator/operator123")
    else:
        print("ℹ️  Sample operator user already exists")
    
    db.session.commit()
    print("✅ User seeding completed")

def update_existing_users_with_roles():
    """Update existing users to have database role assignments"""
    users = User.query.all()
    
    for user in users:
        if not user.role_id:  # Only update users without database roles
            # Map legacy role strings to database roles
            role_name = user.role if hasattr(user, 'role') and user.role else 'organization_owner'
            db_role = Role.query.filter_by(name=role_name).first()
            
            if db_role:
                user.role_id = db_role.id
                print(f"✅ Updated user {user.username} with role: {role_name}")
            else:
                # Default to organization_owner if role not found
                default_role = Role.query.filter_by(name='organization_owner').first()
                if default_role:
                    user.role_id = default_role.id
                    print(f"⚠️  User {user.username} had unknown role '{role_name}', set to organization_owner")
    
    db.session.commit()
    print("✅ Existing users updated with database roles")
