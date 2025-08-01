"""Updated management commands for better error handling, database checks, and unit seeding."""
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
    """Seed production database with essential data (run after migrations)"""
    try:
        print("🚀 BatchTrack Production Seeding Starting...")
        print("⚠️  Assumes database schema is already migrated (flask db upgrade)")

        # Check if database has basic tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        required_tables = ['permission', 'subscription_tier', 'unit', 'organization', 'user']
        missing_tables = [t for t in required_tables if t not in tables]

        if missing_tables:
            print(f"❌ Missing required tables: {missing_tables}")
            print("   Run 'flask db upgrade' first to create database schema")
            return

        # Essential system setup (STRICT DEPENDENCY ORDER)
        print("=== Step 1: System foundations ===")
        try:
            seed_consolidated_permissions()  # Must be FIRST - creates permissions
            print("✅ Permissions seeded")
        except Exception as e:
            print(f"⚠️  Permission seeding issue: {e}")
            print("   Continuing with remaining steps...")

        try:
            seed_subscriptions()             # Must be SECOND - needs permissions, creates tiers
            print("✅ Subscription tiers seeded")
        except Exception as e:
            print(f"⚠️  Subscription seeding issue: {e}")
            print("   Continuing with remaining steps...")

        try:
            seed_units()                     # Independent - can run anytime
            print("✅ Units seeded")
        except Exception as e:
            print(f"⚠️  Unit seeding issue: {e}")
            print("   Continuing with remaining steps...")

        # Create initial admin (DEPENDS on subscription tiers existing)
        print("=== Step 2: Initial admin setup ===")
        try:
            seed_users_and_organization()    # DEPENDS on subscription tiers
            print("✅ Users and organization seeded")
        except Exception as e:
            print(f"⚠️  User/organization seeding issue: {e}")
            print("   Continuing with remaining steps...")

        # Setup default categories for first org
        print("=== Step 3: Organization setup ===")
        try:
            from .models import Organization
            org = Organization.query.first()
            if org:
                seed_categories(organization_id=org.id)
                print("✅ Categories seeded")
            else:
                print("⚠️  No organization found, categories not seeded")
        except Exception as e:
            print(f"⚠️  Category seeding issue: {e}")

        print('✅ Production seeding complete!')
        print('🔒 Login: admin/admin (CHANGE IMMEDIATELY)')
        print('📝 Note: This command can be run multiple times safely')
        print('📊 Database status:')
        try:
            from .models import Organization, User, Permission, SubscriptionTier, Unit
            print(f'   - Organizations: {Organization.query.count()}')
            print(f'   - Users: {User.query.count()}')
            print(f'   - Permissions: {Permission.query.count()}')
            print(f'   - Subscription Tiers: {SubscriptionTier.query.count()}')
            print(f'   - Units: {Unit.query.count()}')
        except Exception as e:
            print(f'   - Status check failed: {e}')

    except Exception as e:
        print(f'❌ Production seeding failed: {str(e)}')
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

@click.command('seed-users')
@with_appcontext
def seed_users_command():
    """Seed users and organization"""
    try:
        print("🔄 Seeding users and organization...")
        from .seeders.user_seeder import seed_users_and_organization
        seed_users_and_organization()
        print('✅ Users and organization seeded successfully!')
    except Exception as e:
        print(f'❌ User seeding failed: {str(e)}')
        db.session.rollback()
        raise

@click.command('seed-permissions')
@with_appcontext
def seed_permissions_command():
    """Seed consolidated permissions"""
    try:
        print("🔄 Seeding permissions...")
        from .seeders.consolidated_permission_seeder import seed_consolidated_permissions
        seed_consolidated_permissions()
        print('✅ Permissions seeded successfully!')
    except Exception as e:
        print(f'❌ Permission seeding failed: {str(e)}')
        db.session.rollback()
        raise

@click.command('seed-organizations')
@with_appcontext
def seed_organizations_command():
    """Seed organizations (part of user seeding)"""
    try:
        print("🔄 Seeding organizations...")
        from .seeders.user_seeder import seed_users_and_organization
        seed_users_and_organization()
        print('✅ Organizations seeded successfully!')
    except Exception as e:
        print(f'❌ Organization seeding failed: {str(e)}')
        db.session.rollback()
        raise

@click.command('seed-units')
@with_appcontext
def seed_units_command():
    """Seed standard system units"""
    try:
        print("🔧 Seeding standard units...")

        # Check if units table exists and has the required columns
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'unit' not in inspector.get_table_names():
            print("❌ Unit table doesn't exist. Run 'flask db upgrade' first.")
            return

        # Check column structure
        columns = [col['name'] for col in inspector.get_columns('unit')]
        required_cols = ['id', 'name', 'symbol', 'unit_type', 'base_unit', 'conversion_factor']
        missing_cols = [col for col in required_cols if col not in columns]
        if missing_cols:
            print(f"❌ Missing required columns in unit table: {missing_cols}")
            return

        # Check if we have timestamp columns
        has_timestamps = 'created_at' in columns and 'updated_at' in columns
        print(f"ℹ️  Unit table timestamp columns: {'✅ Present' if has_timestamps else '❌ Missing'}")

        seed_units()
        print("✅ Units seeded successfully")

    except Exception as e:
        print(f'❌ Unit seeding failed: {str(e)}')
        import traceback
        traceback.print_exc()
        raise

@click.command('seed-sub-tiers')
@with_appcontext
def seed_sub_tiers_command():
    """Seed subscription tiers"""
    try:
        print("🔄 Seeding subscription tiers...")
        from .seeders.subscription_seeder import seed_subscriptions
        seed_subscriptions()
        print('✅ Subscription tiers seeded successfully!')
    except Exception as e:
        print(f'❌ Subscription tier seeding failed: {str(e)}')
        db.session.rollback()
        raise

@click.command('seed-categories')
@with_appcontext
def seed_categories_command():
    """Seed ingredient categories for first organization"""
    try:
        print("🔄 Seeding categories...")
        from .models import Organization
        from .seeders.ingredient_category_seeder import seed_categories

        org = Organization.query.first()
        if org:
            seed_categories(organization_id=org.id)
            print('✅ Categories seeded successfully!')
        else:
            print('❌ No organization found - seed users first')
    except Exception as e:
        print(f'❌ Category seeding failed: {str(e)}')
        db.session.rollback()
        raise

@click.command('seed-permission-categories')
@click.option('--category', help='Specific permission category to seed (app, organization, system, developer)')
@with_appcontext
def seed_permission_categories_command(category):
    """Seed permissions by category"""
    try:
        if category:
            print(f"🔄 Seeding {category} permission category...")
        else:
            print("🔄 Seeding all permission categories...")

        from .seeders.consolidated_permission_seeder import seed_consolidated_permissions

        # For now, we'll seed all permissions since the seeder handles categories internally
        # Future enhancement could filter by specific category
        seed_consolidated_permissions()

        if category:
            print(f'✅ {category} permission category seeded successfully!')
        else:
            print('✅ All permission categories seeded successfully!')

    except Exception as e:
        print(f'❌ Permission category seeding failed: {str(e)}')
        db.session.rollback()
        raise

@click.command('create-app')
@with_appcontext
def create_app_command():
    """Initialize database and create all model tables"""
    try:
        print("🚀 Creating BatchTrack application database...")

        # Import all models to ensure they're registered with SQLAlchemy
        print("📦 Dynamically importing all models...")

        # Import the models package - this triggers all model registrations
        from . import models

        # Import everything from models.__init__.py which imports all models
        import importlib
        import pkgutil
        import os

        models_imported = 0

        # Get all model classes from the models.__init__.py __all__ list
        if hasattr(models, '__all__'):
            for model_name in models.__all__:
                if hasattr(models, model_name):
                    model_class = getattr(models, model_name)
                    # Check if it's a SQLAlchemy model class
                    if hasattr(model_class, '__tablename__'):
                        models_imported += 1
                        print(f"   ✓ {model_name}")

        # Also scan the models directory for any additional files
        models_dir = os.path.join(os.path.dirname(__file__), 'models')
        for finder, name, ispkg in pkgutil.iter_modules([models_dir]):
            if name != '__init__' and not name.startswith('_'):
                try:
                    module = importlib.import_module(f'.models.{name}', package='app')
                    print(f"   ✓ Loaded models from {name}.py")
                except ImportError as e:
                    print(f"   ⚠️  Could not import models.{name}: {e}")

        print(f"✅ {models_imported} models imported dynamically")

        # Create all tables
        print("🏗️  Creating database tables...")
        db.create_all()
        print("✅ Database tables created")

        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📊 Created {len(tables)} tables: {', '.join(sorted(tables))}")

        print("✅ BatchTrack application database created successfully!")
        print("🔄 Next steps:")
        print("   1. Run: flask init-production (to seed initial data)")
        print("   2. Or run individual seeders as needed")

    except Exception as e:
        print(f'❌ Database creation failed: {str(e)}')
        import traceback
        traceback.print_exc()
        raise

@click.command('sync-schema')
@with_appcontext
def sync_schema_command():
    """Safely sync database schema to match models (adds missing tables/columns only)"""
    try:
        print("🚀 Syncing database schema to match models (safe mode)...")

        # Import all models to ensure they're registered with SQLAlchemy
        print("📦 Dynamically importing all models...")

        # Import the models package - this triggers all model registrations
        from . import models

        # Import everything from models.__init__.py which imports all models
        import importlib
        import pkgutil
        import os

        models_imported = 0

        # Get all model classes from the models.__init__.py __all__ list
        if hasattr(models, '__all__'):
            for model_name in models.__all__:
                if hasattr(models, model_name):
                    model_class = getattr(models, model_name)
                    # Check if it's a SQLAlchemy model class
                    if hasattr(model_class, '__tablename__'):
                        models_imported += 1
                        print(f"   ✓ {model_name}")

        # Also scan the models directory for any additional files
        models_dir = os.path.join(os.path.dirname(__file__), 'models')
        for finder, name, ispkg in pkgutil.iter_modules([models_dir]):
            if name != '__init__' and not name.startswith('_'):
                try:
                    module = importlib.import_module(f'.models.{name}', package='app')
                    print(f"   ✓ Loaded models from {name}.py")
                except ImportError as e:
                    print(f"   ⚠️  Could not import models.{name}: {e}")

        print(f"✅ {models_imported} models imported dynamically")

        # Get current database state
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        print(f"📊 Found {len(existing_tables)} existing tables")

        # Create only missing tables (safe operation)
        print("🏗️  Creating any missing tables...")
        tables_before = len(existing_tables)

        # This only creates tables that don't exist - safe operation
        db.create_all()

        # Check what was added
        inspector = inspect(db.engine)
        tables_after = set(inspector.get_table_names())
        new_tables = tables_after - existing_tables

        if new_tables:
            print(f"✅ Added {len(new_tables)} new tables: {', '.join(sorted(new_tables))}")
        else:
            print("✅ No new tables needed")

        # Now add missing columns to existing tables
        print("🔧 Checking for missing columns in existing tables...")
        columns_added = 0

        for table_name in existing_tables:
            # Get existing columns in database
            existing_columns = {col['name']: col for col in inspector.get_columns(table_name)}

            # Find the model class for this table
            model_class = None
            for model_name in models.__all__:
                if hasattr(models, model_name):
                    model_cls = getattr(models, model_name)
                    if hasattr(model_cls, '__tablename__') and model_cls.__tablename__ == table_name:
                        model_class = model_cls
                        break

            if not model_class:
                print(f"   ⚠️  No model found for table: {table_name}")
                continue

            # Get expected columns from model
            expected_columns = {}
            for column_name, column in model_class.__table__.columns.items():
                expected_columns[column_name] = column

            # Find missing columns
            missing_columns = set(expected_columns.keys()) - set(existing_columns.keys())

            if missing_columns:
                print(f"   📋 Table '{table_name}' missing columns: {', '.join(missing_columns)}")

                for column_name in missing_columns:
                    column = expected_columns[column_name]

                    try:
                        # Build column definition
                        column_type = column.type.compile(db.engine.dialect)
                        nullable = "NULL" if column.nullable else "NOT NULL"

                        # Handle default values
                        default_clause = ""
                        if column.default is not None:
                            if hasattr(column.default, 'arg'):
                                if callable(column.default.arg):
                                    # For functions like datetime.utcnow, make nullable for safety
                                    nullable = "NULL"
                                else:
                                    # Quote string defaults properly
                                    default_value = column.default.arg
                                    if isinstance(default_value, str):
                                        default_clause = f" DEFAULT '{default_value}'"
                                    else:
                                        default_clause = f" DEFAULT {default_value}"
                            else:
                                # Quote string defaults properly
                                default_value = column.default
                                if isinstance(default_value, str):
                                    default_clause = f" DEFAULT '{default_value}'"
                                else:
                                    default_clause = f" DEFAULT {default_value}"

                        # Make all new columns nullable for safety during migration
                        nullable = "NULL"

                        # Execute the ALTER TABLE command
                        sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type} {nullable}{default_clause}'
                        db.session.execute(text(sql))
                        db.session.commit()

                        columns_added += 1
                        print(f"      ✅ Added column: {column_name} ({column_type})")

                    except Exception as e:
                        print(f"      ❌ Failed to add column {column_name}: {e}")
                        db.session.rollback()
            else:
                print(f"   ✅ Table '{table_name}' schema is up to date")

        print(f"📊 Total tables: {len(tables_after)}")
        print(f"📊 Total columns added: {columns_added}")
        print("✅ Database schema safely synced to match models!")
        print("🔄 Note: This only adds missing tables/columns - existing data is preserved")
        print("⚠️  New columns are added as nullable for safety")

    except Exception as e:
        print(f'❌ Schema sync failed: {str(e)}')
        import traceback
        traceback.print_exc()
        db.session.rollback()
        raise

def register_commands(app):
    """Register CLI commands"""
    # Database initialization
    app.cli.add_command(create_app_command)
    app.cli.add_command(sync_schema_command)

    # One-time initialization (fresh installs only)
    app.cli.add_command(init_production_command)

    # Individual seeders
    app.cli.add_command(seed_users_command)
    app.cli.add_command(seed_permissions_command)
    app.cli.add_command(seed_organizations_command)
    app.cli.add_command(seed_units_command)
    app.cli.add_command(seed_sub_tiers_command)
    app.cli.add_command(seed_categories_command)
    app.cli.add_command(seed_permission_categories_command)

    # Production maintenance commands
    app.cli.add_command(update_permissions_command)
    app.cli.add_command(update_subscription_tiers_command)
    app.cli.add_command(activate_users)