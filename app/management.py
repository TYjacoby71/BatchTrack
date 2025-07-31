"""
Management commands for deployment and maintenance
"""
import click
from flask import current_app
from flask.cli import with_appcontext
from .extensions import db
from .models import User, Organization, Permission
from .seeders import (
    seed_units,
    seed_categories,
    seed_subscriptions
)
from .seeders.consolidated_permission_seeder import seed_consolidated_permissions
from .seeders.user_seeder import seed_users_and_organization

@click.command()
@with_appcontext  
def seed_all():
    """Seed all initial data in proper order"""
    print("=== SEEDING ALL DATA ===")

    # 1. Consolidated permissions system (permissions + roles)
    seed_consolidated_permissions()

    # 2. Subscription system (creates tiers with proper permissions)
    seed_subscriptions()

    # 3. Basic system data
    seed_units()

    # 4. Users (after permissions and subscriptions exist)
    seed_users_and_organization()

    # 5. Categories (needs organization from users)
    from .models import Organization
    org = Organization.query.first()
    if org:
        seed_categories(organization_id=org.id)

    print("=== ALL SEEDING COMPLETED ===")

@click.command()
@with_appcontext
def init_db():
    """Initialize database with all seeders"""
    try:
        print("🚀 Initializing database...")
        db.create_all()

        # Seed consolidated permissions system first
        seed_consolidated_permissions()

        # Seed core data
        seed_units()
        seed_users_and_organization()

        # Get the organization ID from the first organization
        from .models import Organization
        org = Organization.query.first()
        if org:
            seed_categories(organization_id=org.id)
        else:
            print('❌ No organization found for seeding categories')
            return

        # Seed subscription data
        seed_subscriptions()

        print('✅ Database initialized successfully!')
    except Exception as e:
        print(f'❌ Error initializing database: {str(e)}')
        raise

@click.command('seed-permissions')
@with_appcontext
def seed_permissions_command():
    """Seed consolidated permissions and roles system"""
    try:
        seed_consolidated_permissions()
        print('✅ Consolidated permissions seeded successfully!')
    except Exception as e:
        print(f'❌ Error seeding permissions: {str(e)}')
        raise

@click.command('seed-users')
@with_appcontext
def seed_users_command():
    """Seed users only"""
    try:
        seed_users_and_organization()
        print("✅ Default organization and essential users created successfully!")

        # Verify user types are correct
        verify_user_types()
    except Exception as e:
        print(f'❌ Error seeding users: {str(e)}')
        raise

def verify_user_types():
    """Verify all users have correct types and organization assignments"""
    print("=== Verifying User Types ===")

    # Check developer users
    dev_users = User.query.filter_by(user_type='developer').all()
    for user in dev_users:
        if user.organization_id is not None:
            print(f"❌ CRITICAL: Developer user {user.username} has organization_id={user.organization_id}")
        else:
            print(f"✅ Developer user {user.username} correctly has no organization")

    # Check customer users
    customer_users = User.query.filter_by(user_type='customer').all()
    for user in customer_users:
        if user.organization_id is None:
            print(f"❌ CRITICAL: Customer user {user.username} has no organization_id")
        else:
            print(f"✅ Customer user {user.username} correctly assigned to org {user.organization_id}")

    print(f"📊 Total: {len(dev_users)} developers, {len(customer_users)} customers")

@click.command('seed-subscriptions')
@with_appcontext
def seed_subscriptions_command():
    """Seed subscription data only"""
    try:
        seed_subscriptions()
        print('✅ Subscriptions seeded successfully!')
    except Exception as e:
        print(f'❌ Error seeding subscriptions: {str(e)}')
        raise

@click.command('update-user-roles')
@with_appcontext
def update_user_roles_command():
    """Update existing users with database role assignments"""
    try:
        # update_existing_users_with_roles() removed - users are created properly by seed_users()
        print('✅ User roles updated successfully!')
    except Exception as e:
        print(f'❌ Error updating user roles: {str(e)}')
        raise

@click.command('seed-units')
@with_appcontext
def seed_units_command():
    """Seed only units"""
    try:
        seed_units()
        print('✅ Units seeded!')
    except Exception as e:
        print(f'❌ Error seeding units: {str(e)}')
        raise

@click.command('activate-users')
@with_appcontext
def activate_users():
    """Activate all inactive users"""
    try:
        from .models import User

        inactive_users = User.query.filter_by(is_active=False).all()
        if not inactive_users:
            print("ℹ️  No inactive users found.")
            return

        for user in inactive_users:
            user.is_active = True
            print(f"✅ Activated user: {user.username}")

        db.session.commit()
        print(f"✅ Activated {len(inactive_users)} users.")
    except Exception as e:
        print(f'❌ Error activating users: {str(e)}')
        raise

@click.command('init-production')
@with_appcontext
def init_production_command():
    """Initialize production database with essential data only"""
    try:
        print("🚀 Initializing production database...")

        # Apply migrations
        from flask_migrate import upgrade
        upgrade()

        # CORRECTED SEEDING ORDER - PERMISSIONS MUST BE FULLY SET UP FIRST:
        # 1. Consolidated permissions system (creates permissions AND assigns them to roles)
        print("=== Step 1: Setting up complete permissions system ===")
        seed_consolidated_permissions()

        # 2. Subscription tiers (creates exempt tier)
        print("=== Step 2: Setting up subscription tiers ===")
        seed_subscriptions()

        # 3. Basic system data
        print("=== Step 3: Setting up basic system data ===")
        seed_units()

        # 4. Users (now has all dependencies available)
        print("=== Step 4: Creating users and organization ===")
        seed_users_and_organization()

        # 5. Categories (needs organization from user seeder)
        print("=== Step 5: Setting up categories ===")
        from .models import Organization
        org = Organization.query.first()
        if org:
            seed_categories(organization_id=org.id)
        else:
            print("⚠️  No organization found for categories, skipping...")

        print('✅ Production database initialized successfully!')
        print('🔒 Default users created: admin/admin, dev/dev123')
        print('🔒 Remember to change passwords after first login!')

    except Exception as e:
        print(f'❌ Error initializing production database: {str(e)}')
        raise

@click.command('redeploy-init')
@with_appcontext
def redeploy_init_command():
    """Complete redeployment initialization - safe for production redeployments"""
    try:
        print("🚀 Starting comprehensive redeployment initialization...")

        # Apply any pending migrations with foreign key constraints handled
        from flask_migrate import upgrade
        from sqlalchemy import text
        print("=== Step 1: Applying database migrations ===")
        
        # For SQLite, temporarily disable foreign key constraints
        if 'sqlite' in str(db.engine.url):
            db.session.execute(text("PRAGMA foreign_keys=OFF"))
            db.session.commit()
        
        upgrade()
        
        if 'sqlite' in str(db.engine.url):
            db.session.execute(text("PRAGMA foreign_keys=ON"))
            db.session.commit()

        # Refresh permissions system (updates existing, adds new)
        print("=== Step 2: Refreshing permissions and roles system ===")
        seed_consolidated_permissions()

        # Update subscription tiers (adds new tiers, updates existing)
        print("=== Step 3: Updating subscription tiers ===")
        seed_subscriptions()

        # Ensure system units are up to date
        print("=== Step 4: Updating system units ===")
        seed_units()

        # Ensure default users exist (won't override existing)
        print("=== Step 5: Ensuring default users exist ===")
        seed_users_and_organization()

        # Import User here for verification
        from .models import User

        # Verify role permissions are correctly assigned
        print("=== Step 6: Verifying role permissions ===")
        from .models.role import Role
        from .models import Permission

        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        if org_owner_role:
            # Get ALL active permissions (not just specific categories)
            all_permissions = Permission.query.filter_by(is_active=True).all()

            print(f"Found {len(all_permissions)} active permissions in system")
            print(f"Organization owner role currently has {len(org_owner_role.permissions)} permissions")

            # Always restore all permissions to organization owner
            print("🔧 Restoring all permissions to organization_owner role...")
            org_owner_role.permissions = all_permissions
            db.session.commit()
            print(f"✅ Updated organization_owner role with all {len(all_permissions)} permissions")

        # Update categories for existing organizations
        print("=== Step 7: Updating categories for all organizations ===")
        from .models import Organization
        orgs = Organization.query.all()
        for org in orgs:
            try:
                seed_categories(organization_id=org.id)
                print(f"✅ Updated categories for organization: {org.name}")
            except Exception as e:
                print(f"⚠️  Failed to update categories for {org.name}: {str(e)}")

        print('✅ Redeployment initialization completed successfully!')
        print('🔄 All systems refreshed and verified')

    except Exception as e:
        print(f'❌ Error during redeployment initialization: {str(e)}')
        db.session.rollback()
        raise

@click.command('force-sync-tiers')
@with_appcontext
def force_sync_tiers_command():
    """FORCE sync subscription tiers from JSON - OVERWRITES existing configurations"""
    try:
        print("⚠️  WARNING: This will overwrite existing subscription tier configurations!")
        confirm = input("Type 'YES' to continue: ")

        if confirm != 'YES':
            print("❌ Operation cancelled")
            return

        from .seeders.subscription_seeder import force_sync_tiers_from_json
        force_sync_tiers_from_json()

        print('✅ Force sync completed successfully!')
        print('🔄 All subscription tiers have been updated from JSON configuration')

    except Exception as e:
        print(f'❌ Error during force sync: {str(e)}')
        db.session.rollback()
        raise

def register_commands(app):
    """Register CLI commands"""
    app.cli.add_command(seed_all)
    app.cli.add_command(init_db)
    app.cli.add_command(seed_permissions_command)
    app.cli.add_command(seed_users_command)
    app.cli.add_command(seed_subscriptions_command)
    app.cli.add_command(seed_units_command)
    app.cli.add_command(update_user_roles_command)
    app.cli.add_command(activate_users)
    app.cli.add_command(init_production_command)
    app.cli.add_command(redeploy_init_command)
    app.cli.add_command(force_sync_tiers_command)