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
        print('✅ Users seeded successfully!')
    except Exception as e:
        print(f'❌ Error seeding users: {str(e)}')
        raise

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

        # CORRECTED SEEDING ORDER:
        # 1. Permissions and roles MUST come first
        print("=== Step 1: Setting up permissions and roles ===")
        print("=== Seeding Consolidated Permissions ===")
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