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
    """THE SINGLE LAUNCH COMMAND - Initialize production database with all essential data"""
    try:
        print("🚀 BatchTrack Production Initialization Starting...")

        # Apply migrations first
        from flask_migrate import upgrade
        from sqlalchemy import text
        print("=== Step 1: Applying database migrations ===")
        
        # Handle foreign key constraints for SQLite
        if 'sqlite' in str(db.engine.url):
            db.session.execute(text("PRAGMA foreign_keys=OFF"))
            db.session.commit()
        
        upgrade()
        
        if 'sqlite' in str(db.engine.url):
            db.session.execute(text("PRAGMA foreign_keys=ON"))
            db.session.commit()

        # Complete system setup in correct order
        print("=== Step 2: Setting up permissions system ===")
        seed_consolidated_permissions()

        print("=== Step 3: Setting up subscription tiers ===")
        seed_subscriptions()

        print("=== Step 4: Setting up basic system data ===")
        seed_units()

        print("=== Step 5: Creating users and organization ===")
        seed_users_and_organization()

        print("=== Step 6: Setting up categories ===")
        from .models import Organization
        org = Organization.query.first()
        if org:
            seed_categories(organization_id=org.id)
            print(f"✅ Categories created for organization: {org.name}")
        else:
            print("⚠️  No organization found, skipping categories...")

        # Verify setup
        print("=== Step 7: Verifying setup ===")
        from .models import User, Permission
        
        user_count = User.query.count()
        permission_count = Permission.query.filter_by(is_active=True).count()
        org_count = Organization.query.count()
        
        print(f"📊 Setup complete:")
        print(f"   - Organizations: {org_count}")
        print(f"   - Users: {user_count}")
        print(f"   - Active permissions: {permission_count}")

        print('✅ BatchTrack Production Ready!')
        print('🔒 Default login: admin/admin (change password after first login)')
        print('🌐 Your application is ready to use!')

    except Exception as e:
        print(f'❌ Error during initialization: {str(e)}')
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
    # Main launch command
    app.cli.add_command(init_production_command)
    
    # Utility commands for maintenance
    app.cli.add_command(activate_users)
    app.cli.add_command(force_sync_tiers_command)