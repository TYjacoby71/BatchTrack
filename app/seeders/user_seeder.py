
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
    
    # Get roles from database
    developer_role = Role.query.filter_by(name='developer').first()
    org_owner_role = Role.query.filter_by(name='organization_owner').first()
    
    # Create developer user if it doesn't exist
    if not User.query.filter_by(username='dev').first():
        developer_user = User(
            username='dev',
            password_hash=generate_password_hash('dev123'),
            role='developer',  # Keep legacy role for backward compatibility
            role_id=developer_role.id if developer_role else None,  # New database role
            first_name='System',
            last_name='Developer',
            email='dev@batchtrack.com',
            phone='000-000-0000',
            organization_id=org.id,
            is_owner=False  # Developers are not org owners
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
            role='organization_owner',  # Keep legacy role for backward compatibility
            role_id=org_owner_role.id if org_owner_role else None,  # New database role
            first_name='Jacob',
            last_name='Boulette',
            email='jacobboulette@outlook.com',
            phone='775-934-5968',
            organization_id=org.id,
            is_owner=True  # Boolean value for organization owner
        )
        db.session.add(admin_user)
        print("✅ Created organization owner user: admin/admin")
    else:
        print("ℹ️  Admin user already exists")
    
    # Create a sample organization_owner (maker) user if it doesn't exist
    if not User.query.filter_by(username='maker').first():
        maker_user = User(
            username='maker',
            password_hash=generate_password_hash('maker123'),
            role='organization_owner',  # Keep legacy role for backward compatibility
            role_id=org_owner_role.id if org_owner_role else None,  # New database role
            first_name='Sample',
            last_name='Maker',
            email='maker@example.com',
            phone='555-0123',
            organization_id=org.id,
            is_owner=True  # Boolean value - organization owner
        )
        db.session.add(maker_user)
        print("✅ Created sample maker user: maker/maker123")
    else:
        print("ℹ️  Sample maker user already exists")
    
    db.session.commit()
    print("✅ User seeding completed")

def update_existing_users_with_roles():
    """Update existing users to have database role assignments"""
    users = User.query.all()
    
    for user in users:
        if not user.role_id:  # Only update users without database roles
            # Map legacy role strings to database roles
            role_name = user.role
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
