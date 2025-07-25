"""
Management commands for deployment and maintenance
"""
import click
from flask.cli import with_appcontext
from .extensions import db
from .seeders import (
    seed_units, 
    seed_categories, 
    seed_users, 
    seed_consolidated_permissions,
    seed_subscriptions
)
from .seeders.user_seeder import update_existing_users_with_roles

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
        seed_users()

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

@click.command('seed-all')
@with_appcontext
def seed_all_command():
    """Seed all data"""
    try:
        print("🌱 Seeding all data...")

        # First seed the consolidated permissions system
        seed_consolidated_permissions()

        # Core seeders
        seed_units()
        seed_users()

        # Get the organization ID from the first organization
        from .models import Organization
        org = Organization.query.first()
        if org:
            seed_categories(organization_id=org.id)
        else:
            print('❌ No organization found for seeding categories')
            return

        # Update existing users with database roles
        update_existing_users_with_roles()

        # Seed subscription data
        seed_subscriptions()

        print('✅ All data seeded successfully!')
    except Exception as e:
        print(f'❌ Error seeding data: {str(e)}')
        raise

@click.command('seed-permissions')
@with_appcontext
def seed_permissions_command():
    """Seed permissions and roles only"""
    try:
        seed_consolidated_permissions()
        print('✅ Permissions seeded successfully!')
    except Exception as e:
        print(f'❌ Error seeding permissions: {str(e)}')
        raise

@click.command('seed-users')
@with_appcontext
def seed_users_command():
    """Seed users only"""
    try:
        seed_users()
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
        update_existing_users_with_roles()
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

        # Use existing comprehensive seeders
        seed_consolidated_permissions()
        seed_units()
        seed_users()  # This already creates exempt org + admin user

        # Get the organization ID for categories
        from .models import Organization
        org = Organization.query.first()
        if org:
            seed_categories(organization_id=org.id)

        # Seed subscription data
        seed_subscriptions()

        print('✅ Production database initialized successfully!')
        print('🔒 Default users created: admin/admin, dev/dev123')
        print('🔒 Remember to change passwords after first login!')

    except Exception as e:
        print(f'❌ Error initializing production database: {str(e)}')
        raise

def register_commands(app):
    """Register CLI commands with the app"""
    app.cli.add_command(init_db)
    app.cli.add_command(seed_all_command)
    app.cli.add_command(seed_permissions_command)
    app.cli.add_command(seed_users_command)
    app.cli.add_command(seed_subscriptions_command)
    app.cli.add_command(seed_units_command)
    app.cli.add_command(update_user_roles_command)
    app.cli.add_command(activate_users)