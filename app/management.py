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
    """ONE-TIME ONLY: Initialize fresh production database"""
    try:
        # Check if already initialized
        from .models import Organization, User
        if Organization.query.first() or User.query.first():
            print("❌ Database already initialized! Use migrations for updates.")
            print("   - For permission updates: flask db migrate && flask db upgrade")
            print("   - For new features: Create proper migrations")
            return

        print("🚀 BatchTrack Fresh Installation Starting...")

        # Apply migrations
        from flask_migrate import upgrade
        print("=== Step 1: Database migrations ===")
        upgrade()

        # One-time system setup
        print("=== Step 2: System foundations ===")
        seed_consolidated_permissions()
        seed_subscriptions()
        seed_units()

        # Create initial admin
        print("=== Step 3: Initial admin setup ===")
        seed_users_and_organization()

        # Setup default categories for first org
        from .models import Organization
        org = Organization.query.first()
        if org:
            seed_categories(organization_id=org.id)

        print('✅ Fresh installation complete!')
        print('🔒 Login: admin/admin (CHANGE IMMEDIATELY)')
        print('⚠️  This command will refuse to run again - use migrations for updates')

    except Exception as e:
        print(f'❌ Initialization failed: {str(e)}')
        db.session.rollback()
        raise



@click.command('update-permissions')
@with_appcontext  
def update_permissions_command():
    """Update permissions from consolidated JSON (production-safe)"""
    try:
        print("🔄 Updating permissions from consolidated_permissions.json...")
        
        from .seeders.consolidated_permission_seeder import seed_consolidated_permissions
        seed_consolidated_permissions()
        
        print('✅ Permissions updated successfully!')
        print('   - New permissions added')
        print('   - Existing permissions updated')
        print('   - Old permissions deactivated')
        
    except Exception as e:
        print(f'❌ Permission update failed: {str(e)}')
        db.session.rollback()
        raise

@click.command('update-subscription-tiers')
@with_appcontext
def update_subscription_tiers_command():
    """Update subscription tiers (production-safe)"""
    try:
        print("🔄 Updating subscription tiers...")
        
        from .seeders.subscription_seeder import seed_subscriptions
        seed_subscriptions()  # This should be update-safe
        
        print('✅ Subscription tiers updated!')
        
    except Exception as e:
        print(f'❌ Subscription tier update failed: {str(e)}')
        db.session.rollback()
        raise

def register_commands(app):
    """Register CLI commands"""
    # One-time initialization (fresh installs only)
    app.cli.add_command(init_production_command)
    
    # Production maintenance commands
    app.cli.add_command(update_permissions_command)
    app.cli.add_command(update_subscription_tiers_command)
    app.cli.add_command(activate_users)