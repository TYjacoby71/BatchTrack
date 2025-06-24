
"""
Management commands for deployment and maintenance
"""
import click
from flask.cli import with_appcontext
from .extensions import db
from .seeders import seed_units, seed_categories, seed_users

@click.command()
@with_appcontext
def init_db():
    """Initialize database with all seeders"""
    db.create_all()
    seed_units()
    seed_categories()
    seed_users()
    click.echo('✅ Database initialized successfully!')

@click.command()
@with_appcontext
def seed_all():
    """Run all seeders"""
    seed_units()
    seed_categories()
    seed_users()
    click.echo('✅ All seeders completed!')

@click.command()
@with_appcontext
def seed_units_only():
    """Seed only units"""
    seed_units()
    click.echo('✅ Units seeded!')

def register_commands(app):
    """Register CLI commands with the app"""
    app.cli.add_command(init_db)
    app.cli.add_command(seed_all)
    app.cli.add_command(seed_units_only)
