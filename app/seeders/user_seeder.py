
from ..models import User, Organization, Role
from ..extensions import db
from werkzeug.security import generate_password_hash

def seed_users_and_organization():
    """Create the default BatchTrack organization with 4 essential users"""
    from flask import current_app

    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_users_and_organization() must be called within Flask application context")

    from app.models.role import Role
    from ..models.developer_role import DeveloperRole
    from ..models.user_role_assignment import UserRoleAssignment
    from ..models.subscription_tier import SubscriptionTier

    print("=== Creating Default Organization with Essential Users ===")

    # Check if this is a fresh installation or re-initialization
    existing_orgs = Organization.query.count()
    
    if existing_orgs > 0:
        print(f"ℹ️  Found {existing_orgs} existing organizations - using first organization")
        org = Organization.query.first()
    else:
        print("ℹ️  No organizations found - creating default organization")
        
        # Get the exempt tier (must exist from subscription seeder)
        exempt_tier = SubscriptionTier.query.filter_by(key='exempt').first()
        if not exempt_tier:
            print("❌ Exempt tier not found! Run subscription seeder first.")
            return
            
        # Create the default BatchTrack organization
        org = Organization(
            name='BatchTrack Organization',
            contact_email='admin@batchtrack.com',
            subscription_tier_id=exempt_tier.id,
            is_active=True
        )
        db.session.add(org)
        db.session.flush()
        print(f"✅ Created default organization: {org.name} (ID: {org.id})")

    print(f"ℹ️  Using organization: {org.name} (ID: {org.id})")
    if org.tier:
        print(f"   - Subscription tier: {org.tier.key} ({org.tier.name})")

    # Get required roles
    org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
    manager_role = Role.query.filter_by(name='manager').first()
    operator_role = Role.query.filter_by(name='operator').first()
    system_admin_dev_role = DeveloperRole.query.filter_by(name='system_admin').first()

    if not org_owner_role:
        print("❌ organization_owner role not found! Run consolidated permissions seeder first.")
        return

    # 1. Create developer user (system-wide, no organization)
    if not User.query.filter_by(username='dev').first():
        developer_user = User(
            username='dev',
            password_hash=generate_password_hash('dev123'),
            first_name='System',
            last_name='Developer',
            email='dev@batchtrack.com',
            phone='000-000-0000',
            organization_id=None,  # Developers exist outside organizations
            user_type='developer',
            is_active=True
        )
        db.session.add(developer_user)
        db.session.flush()

        # Assign system_admin developer role
        if system_admin_dev_role:
            assignment = UserRoleAssignment(
                user_id=developer_user.id,
                developer_role_id=system_admin_dev_role.id,
                organization_id=None,
                is_active=True
            )
            db.session.add(assignment)
            print(f"✅ Created developer user: dev/dev123 with system_admin role")
        else:
            print(f"✅ Created developer user: dev/dev123 (no system_admin role found)")
    else:
        print(f"ℹ️  Developer user 'dev' already exists")

    # 2. Create admin user (organization owner)
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin'),
            first_name='Jacob',
            last_name='Boulette',
            email='jacobboulette@outlook.com',
            phone='775-934-5968',
            organization_id=org.id,
            user_type='customer',
            is_organization_owner=True,  # This triggers role assignment
            is_active=True
        )
        db.session.add(admin_user)
        db.session.flush()

        # Assign organization owner role
        admin_user.assign_role(org_owner_role)
        print(f"✅ Created admin user: admin/admin (organization owner)")
    else:
        print(f"ℹ️  Admin user 'admin' already exists")

    # 3. Create manager user
    if not User.query.filter_by(username='manager').first():
        manager_user = User(
            username='manager',
            password_hash=generate_password_hash('manager123'),
            first_name='Sample',
            last_name='Manager',
            email='manager@example.com',
            phone='555-0124',
            organization_id=org.id,
            user_type='customer',
            is_organization_owner=False,
            is_active=True
        )
        db.session.add(manager_user)
        db.session.flush()

        # Assign manager role if it exists
        if manager_role:
            manager_user.assign_role(manager_role)
            print(f"✅ Created manager user: manager/manager123 with manager role")
        else:
            print(f"✅ Created manager user: manager/manager123 (no manager role found)")
    else:
        print(f"ℹ️  Manager user 'manager' already exists")

    # 4. Create operator user
    if not User.query.filter_by(username='operator').first():
        operator_user = User(
            username='operator',
            password_hash=generate_password_hash('operator123'),
            first_name='Sample',
            last_name='Operator',
            email='operator@example.com',
            phone='555-0125',
            organization_id=org.id,
            user_type='customer',
            is_organization_owner=False,
            is_active=True
        )
        db.session.add(operator_user)
        db.session.flush()

        # Assign operator role if it exists
        if operator_role:
            operator_user.assign_role(operator_role)
            print(f"✅ Created operator user: operator/operator123 with operator role")
        else:
            print(f"✅ Created operator user: operator/operator123 (no operator role found)")
    else:
        print(f"ℹ️  Operator user 'operator' already exists")

    db.session.commit()
    print("✅ Default organization and essential users created successfully")
    print(f"   - Organization: {org.name} (Exempt tier)")
    print(f"   - 1 System developer (dev/dev123)")
    print(f"   - 3 Organization users (admin, manager, operator)")

# Maintain backward compatibility
def seed_users():
    """Backward compatibility wrapper"""
    return seed_users_and_organization()
