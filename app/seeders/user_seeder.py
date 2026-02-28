import logging
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import Organization, User

logger = logging.getLogger(__name__)



def seed_users_and_organization():
    """Create the default BatchTrack organization with 4 essential users"""
    from flask import current_app

    if not current_app:
        raise RuntimeError(
            "seed_users_and_organization() must be called within Flask application context"
        )

    from app.models.role import Role

    from ..models.developer_role import DeveloperRole
    from ..models.subscription_tier import SubscriptionTier
    from ..models.user_role_assignment import UserRoleAssignment

    print("🔧 Seeding users and organization...")

    # Check if this is a fresh installation or re-initialization
    existing_orgs = Organization.query.count()

    if existing_orgs > 0:
        print(
            f"ℹ️  Found {existing_orgs} existing organizations - using first organization"
        )
        org = Organization.query.first()
    else:
        print("ℹ️  No organizations found - creating default organization")

        # Get the exempt tier (must exist from subscription seeder)
        exempt_tier = SubscriptionTier.query.filter_by(name="Exempt Plan").first()
        if not exempt_tier:
            print("❌ Exempt tier not found! Run subscription seeder first.")
            return

        # Create the default BatchTrack organization
        # Note: contact_email will be set to organization owner's email after user creation
        org = Organization(
            name="BatchTrack Organization",
            subscription_tier_id=exempt_tier.id,
            is_active=True,
        )
        db.session.add(org)
        db.session.flush()
        print(f"✅ Created default organization: {org.name} (ID: {org.id})")

    print(f"ℹ️  Using organization: {org.name} (ID: {org.id})")
    if org.tier:
        print(f"   - Subscription tier: {org.tier.id} ({org.tier.name})")

    # Get required roles
    org_owner_role = Role.query.filter_by(
        name="organization_owner", is_system_role=True
    ).first()
    manager_role = Role.query.filter_by(name="manager").first()
    operator_role = Role.query.filter_by(name="operator").first()
    system_admin_dev_role = DeveloperRole.query.filter_by(name="system_admin").first()

    if not org_owner_role:
        print(
            "❌ organization_owner role not found! Run consolidated permissions seeder first."
        )
        return

    # CRITICAL: Verify developer roles exist
    if not system_admin_dev_role:
        print("❌ system_admin developer role not found!")
        print("   This means developer roles weren't seeded before user creation.")
        print("   Developer user will be created without role assignment.")
    else:
        print(f"✅ Found system_admin developer role (ID: {system_admin_dev_role.id})")

    # 1. Create developer user (system-wide, no organization)
    if not User.query.filter_by(username="dev").first():
        try:
            developer_user = User(
                username="dev",
                password_hash=generate_password_hash("dev123"),
                first_name="System",
                last_name="Developer",
                email="dev@batchtrack.com",
                phone="000-000-0000",
                organization_id=None,  # Developers exist outside organizations - NEVER set org_id
                user_type="developer",  # Must be 'developer' type
                is_active=True,
            )
            db.session.add(developer_user)
            db.session.flush()

            # Assign system_admin developer role
            if system_admin_dev_role:
                try:
                    assignment = UserRoleAssignment(
                        user_id=developer_user.id,
                        developer_role_id=system_admin_dev_role.id,
                        role_id=None,  # Explicitly set to None for developer roles
                        organization_id=None,  # CRITICAL: Developers NEVER get organization_id
                        is_active=True,
                    )
                    db.session.add(assignment)
                    db.session.flush()  # Flush to catch constraint errors early
                    print(
                        "✅ Created developer user: dev/dev123 with system_admin role"
                    )
                except Exception as role_error:
                    logger.warning("Suppressed exception fallback at app/seeders/user_seeder.py:110", exc_info=True)
                    print(f"⚠️  Developer role assignment failed: {role_error}")
                    print(
                        "✅ Created developer user: dev/dev123 (role assignment failed)"
                    )
                    # Don't rollback here - let the user creation succeed even if role assignment fails
            else:
                print(
                    "✅ Created developer user: dev/dev123 (no system_admin role found)"
                )
        except Exception as user_error:
            logger.warning("Suppressed exception fallback at app/seeders/user_seeder.py:120", exc_info=True)
            print(f"❌ Failed to create developer user: {user_error}")
            db.session.rollback()
    else:
        print("ℹ️  Developer user 'dev' already exists")

    # 2. Create admin user (organization owner)
    existing_admin = User.query.filter_by(username="admin").first()
    if not existing_admin:
        admin_user = User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            first_name="Jacob",
            last_name="Boulette",
            email="jacobboulette@outlook.com",
            phone="775-934-5968",
            organization_id=org.id,
            user_type="customer",
            is_organization_owner=True,  # This triggers role assignment
            is_active=True,
        )
        db.session.add(admin_user)
        db.session.flush()

        # Assign organization owner role
        admin_user.assign_role(org_owner_role)

        # Set organization contact email to admin user's email
        if not org.contact_email:
            org.contact_email = admin_user.email
            print(f"✅ Set organization contact_email to: {admin_user.email}")

        print("✅ Created admin user: admin/admin (organization owner)")
    else:
        admin_user = existing_admin
        # CRITICAL: Do NOT change organization_id on existing admin user
        print(
            f"ℹ️  Admin user 'admin' already exists (org_id: {admin_user.organization_id})"
        )

        # Only update organization contact_email if it's missing
        if not org.contact_email:
            org.contact_email = admin_user.email
            print(f"✅ Updated organization contact_email to: {admin_user.email}")

        # Ensure admin has organization owner role assignment if missing
        from ..models.user_role_assignment import UserRoleAssignment

        existing_assignment = UserRoleAssignment.query.filter_by(
            user_id=admin_user.id,
            role_id=org_owner_role.id if org_owner_role else None,
            is_active=True,
        ).first()

        if not existing_assignment and org_owner_role:
            admin_user.assign_role(org_owner_role)
            print("✅ Assigned missing organization owner role to existing admin")

    # 3. Create manager user
    existing_manager = User.query.filter_by(username="manager").first()
    if not existing_manager:
        manager_user = User(
            username="manager",
            password_hash=generate_password_hash("manager123"),
            first_name="Sample",
            last_name="Manager",
            email="manager@example.com",
            phone="555-0124",
            organization_id=org.id,
            user_type="customer",
            is_organization_owner=False,
            is_active=True,
        )
        db.session.add(manager_user)
        db.session.flush()

        # Assign manager role if it exists
        if manager_role:
            manager_user.assign_role(manager_role)
            print("✅ Created manager user: manager/manager123 with manager role")
        else:
            print("✅ Created manager user: manager/manager123 (no manager role found)")
    else:
        print(
            f"ℹ️  Manager user 'manager' already exists (org_id: {existing_manager.organization_id})"
        )

    # 4. Create operator user
    existing_operator = User.query.filter_by(username="operator").first()
    if not existing_operator:
        operator_user = User(
            username="operator",
            password_hash=generate_password_hash("operator123"),
            first_name="Sample",
            last_name="Operator",
            email="operator@example.com",
            phone="555-0125",
            organization_id=org.id,
            user_type="customer",
            is_organization_owner=False,
            is_active=True,
        )
        db.session.add(operator_user)
        db.session.flush()

        # Assign operator role if it exists
        if operator_role:
            operator_user.assign_role(operator_role)
            print("✅ Created operator user: operator/operator123 with operator role")
        else:
            print(
                "✅ Created operator user: operator/operator123 (no operator role found)"
            )
    else:
        print(
            f"ℹ️  Operator user 'operator' already exists (org_id: {existing_operator.organization_id})"
        )

    db.session.commit()
    print("   ✅ Users and organization: 1 org, 4 users created")


# Maintain backward compatibility
def seed_users():
    """Backward compatibility wrapper"""
    return seed_users_and_organization()
