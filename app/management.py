"""
Management commands for deployment and maintenance
"""
import click
from flask.cli import with_appcontext
from .extensions import db
from .seeders import seed_units, seed_categories, seed_users
from .seeders.user_seeder import update_existing_users_with_roles
from .seeders.role_permission_seeder import seed_roles_and_permissions

@click.command()
@with_appcontext
def init_db():
    """Initialize database with all seeders"""
    db.create_all()
    seed_units()
    seed_categories()
    seed_users()
    click.echo('✅ Database initialized successfully!')

@click.command('seed-all')
@with_appcontext
def seed_all_command():
    """Seed all data"""
    try:
        # First seed roles and permissions
        seed_roles_and_permissions()

        seed_units()
        
        # Seed users first to create organization
        seed_users()
        
        # Get the organization ID from the first organization
        from .models import Organization
        org = Organization.query.first()
        if org:
            seed_categories(organization_id=org.id)
        else:
            click.echo('❌ No organization found for seeding categories')
            return

        # Update existing users with database roles
        update_existing_users_with_roles()

        click.echo('✅ All data seeded successfully!')
    except Exception as e:
        click.echo(f'❌ Error seeding data: {str(e)}')
        raise

@click.command('seed-roles-permissions')
@with_appcontext
def seed_roles_permissions_command():
    """Seed roles and permissions only"""
    try:
        seed_roles_and_permissions()
        click.echo('✅ Roles and permissions seeded successfully!')
    except Exception as e:
        click.echo(f'❌ Error seeding roles and permissions: {str(e)}')
        raise

@click.command('seed-users')
@with_appcontext
def seed_users_command():
    """Seed users only"""
    try:
        seed_users()
        click.echo('✅ Users seeded successfully!')
    except Exception as e:
        click.echo(f'❌ Error seeding users: {str(e)}')
        raise

@click.command('update-user-roles')
@with_appcontext
def update_user_roles_command():
    """Update existing users with database role assignments"""
    try:
        update_existing_users_with_roles()
        click.echo('✅ User roles updated successfully!')
    except Exception as e:
        click.echo(f'❌ Error updating user roles: {str(e)}')
        raise

@click.command()
@with_appcontext
def seed_units_only():
    """Seed only units"""
    seed_units()
    click.echo('✅ Units seeded!')

def register_commands(app):
    """Register CLI commands with the app"""
    app.cli.add_command(init_db)
    app.cli.add_command(seed_all_command)
    app.cli.add_command(seed_units_only)
    app.cli.add_command(seed_roles_permissions_command)
    app.cli.add_command(seed_users_command)
    app.cli.add_command(update_user_roles_command)