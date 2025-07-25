from ..models import User, Organization, Role
from ..extensions import db
from werkzeug.security import generate_password_hash

def seed_users():
    """Seed 4 essential users: dev (developer), admin (exempt org owner), manager, operator"""
    from flask import current_app

    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_users() must be called within Flask application context")

    from app.models.role import Role
    from ..models.developer_role import DeveloperRole
    from ..models.user_role_assignment import UserRoleAssignment

    print("=== Seeding Essential Users ===")

    # Get or create the organization
    from ..models.subscription_tier import SubscriptionTier
    
    org = Organization.query.first()
    if not org:
        print("ℹ️  No organization found, creating default organization...")
        
        # Get the exempt tier
        exempt_tier = SubscriptionTier.query.filter_by(key='exempt').first()
        if not exempt_tier:
            print("❌ Exempt tier not found! Run subscription seeder first.")
            return
            
        # Create default organization
        org = Organization(
            name='BatchTrack Organization',
            subscription_tier_id=exempt_tier.id,
            is_active=True
        )
        db.session.add(org)
        db.session.flush()
        print(f"✅ Created default organization: {org.name}")
    else:
        print(f"ℹ️  Found existing organization: {org.name}")

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

    # 1. Create developer user (no organization)
    if not User.query.filter_by(username='dev').first():
        developer_user = User(
            username='dev',
            password_hash=generate_password_hash('dev123'),
            first_name='System',
            last_name='Developer',
            email='dev@batchtrack.com',
            phone='000-000-0000',
            organization_id=None,  # Developers don't belong to organizations
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

    # 2. Create admin user (organization owner with exempt tier)
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
            is_organization_owner=True,
            is_active=True
        )
        db.session.add(admin_user)
        db.session.flush()

        # Assign organization owner role
        admin_user.assign_role(org_owner_role)
        print(f"✅ Created admin user: admin/admin (org owner)")
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
    print("✅ Essential users seeded successfully")

# update_existing_users_with_roles() removed - no longer needed since 
# seed_users() creates users with proper roles from scratch