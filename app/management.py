"""CLI management commands for deployment, seeding, and maintenance.

Synopsis:
Defines one-time initialization plus update-safe refresh commands for core data.

Glossary:
- Seeder: Idempotent routine that upserts reference data.
- Maintenance command: CLI action for production-safe updates.
"""
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext
from .extensions import db
from .models import User, Organization, Permission
from .seeders import (
    seed_app_settings,
    seed_feature_flags,
    seed_units,
    seed_subscriptions
)
from .seeders.addon_seeder import seed_addons
from .seeders.consolidated_permission_seeder import seed_consolidated_permissions
from .seeders.user_seeder import seed_users_and_organization

# Import text from sqlalchemy for raw SQL execution
from sqlalchemy import text

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
        print("=== Step 1: System foundations (Organization Independent) ===")

        # CRITICAL: Seed permissions and developer roles FIRST
        try:
            seed_consolidated_permissions()  # Must be FIRST - creates permissions, org roles, AND developer roles
            print("✅ Permissions, organization roles, and developer roles seeded")
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
            seed_feature_flags()            # Independent - seeds feature flag defaults
            print("✅ Feature flags seeded")
        except Exception as e:
            print(f"⚠️  Feature flag seeding issue: {e}")
            print("   Continuing with remaining steps...")

        try:
            seed_app_settings()            # Independent - seeds default settings
            print("✅ App settings seeded")
        except Exception as e:
            print(f"⚠️  App settings seeding issue: {e}")
            print("   Continuing with remaining steps...")

        # Add-ons registry (independent)
        try:
            seed_addons()
            print("✅ Add-ons seeded")
            try:
                from .seeders.addon_seeder import backfill_addon_permissions
                backfill_addon_permissions()
            except Exception as e:
                print(f"⚠️  Add-on permission backfill issue: {e}")
        except Exception as e:
            print(f"⚠️  Add-on seeding issue: {e}")
            print("   Continuing with remaining steps...")

        try:
            seed_units()                     # Independent - can run anytime
            print("✅ Units seeded")
        except Exception as e:
            print(f"⚠️  Unit seeding issue: {e}")
            print("   Continuing with remaining steps...")

        # Create organization and users (DEPENDS on system foundations)
        print("=== Step 2: Organization-dependent setup ===")
        print("ℹ️  Developer roles should now exist for user assignment...")
        try:
            seed_users_and_organization()    # Creates org + users (DEPENDS on tiers & developer roles)
            print("✅ Organization and users seeded")
        except Exception as e:
            print(f"⚠️  User/organization seeding issue: {e}")
            print("   Continuing with remaining steps...")

        # Organization-specific setup will be handled by global inventory library seeding
        print("=== Step 3: Organization-specific data ===")
        print("   Categories will be created by global inventory library seeding...")

        # Seed global product categories (not organization-specific)
        try:
            from .seeders.product_category_seeder import seed_product_categories
            seed_product_categories()
            print("✅ Product categories seeded")
        except Exception as e:
            print(f"⚠️  Product category seeding issue: {e}")

        # Seed global inventory library (ingredients, containers, packaging, consumables)
        try:
            from .seeders.seed_global_inventory_library import seed_global_inventory_library
            seed_global_inventory_library()
            print("✅ Global inventory library seeded")
        except Exception as e:
            print(f"⚠️  Global inventory library seeding issue: {e}")

        print('\n📊 Production Seeding Summary:')
        try:
            try:
                db.session.rollback()
            except Exception:
                pass
            from .models import (
                Organization, User, Permission, SubscriptionTier, Unit, 
                DeveloperPermission, DeveloperRole, Role, GlobalItem, 
                IngredientCategory, ProductCategory, Addon
            )

            # System foundations
            org_permissions = Permission.query.filter_by(is_active=True).count()
            dev_permissions = DeveloperPermission.query.filter_by(is_active=True).count()
            dev_roles = DeveloperRole.query.filter_by(is_active=True).count()
            system_roles = Role.query.filter_by(is_system_role=True).count()
            sub_tiers = SubscriptionTier.query.count()
            addons = Addon.query.filter_by(is_active=True).count()
            units = Unit.query.count()

            # Organizations and users
            organizations = Organization.query.count()
            total_users = User.query.count()
            dev_users = User.query.filter_by(user_type='developer').count()
            customer_users = User.query.filter_by(user_type='customer').count()

            # Data catalogs
            ingredient_categories = IngredientCategory.query.count()
            product_categories = ProductCategory.query.count()
            ingredients_count = GlobalItem.query.filter_by(item_type='ingredient').count()
            containers_count = GlobalItem.query.filter_by(item_type='container').count()
            packaging_count = GlobalItem.query.filter_by(item_type='packaging').count()
            consumables_count = GlobalItem.query.filter_by(item_type='consumable').count()
            total_global_items = GlobalItem.query.count()

            print(f'  System:     {org_permissions} org perms, {dev_permissions} dev perms, {dev_roles} dev roles')
            print(f'  Platform:   {sub_tiers} tiers, {addons} addons, {units} units')
            print(f'  Users:      {organizations} orgs, {total_users} users ({dev_users} dev, {customer_users} customer)')
            print(f'  Catalogs:   {ingredient_categories} ingredient cats, {product_categories} product cats')
            print(f'  Library:    {total_global_items} global items ({ingredients_count} ingredients, {containers_count} containers, {packaging_count} packaging, {consumables_count} consumables)')

            print('\n✅ Production seeding complete!')
            print('🔒 Login: admin/admin (CHANGE IMMEDIATELY)')
            print('📝 Note: This command can be run multiple times safely')

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


@click.command('update-addons')
@with_appcontext
def update_addons_command():
    """Update add-ons from addon_seeder (production-safe)"""
    try:
        print("🔄 Updating add-ons from addon_seeder...")

        from .seeders.addon_seeder import seed_addons, backfill_addon_permissions
        seed_addons()
        backfill_addon_permissions()

        print('✅ Add-ons updated successfully!')
        print('   - New add-ons added')
        print('   - Existing add-ons updated')
        print('   - Tier add-on permissions backfilled')

    except Exception as e:
        print(f'❌ Add-on update failed: {str(e)}')
        db.session.rollback()
        raise

@click.command('update-subscription-tiers')
@with_appcontext
def update_subscription_tiers_command():
    """Update subscription tiers (production-safe)"""
    try:
        print("🔄 Updating subscription tiers...")

        from .seeders.subscription_seeder import seed_subscription_tiers
        seed_subscription_tiers()  # This should be update-safe

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
        from .seeders.subscription_seeder import seed_subscription_tiers
        seed_subscription_tiers()
        print('✅ Subscription tiers seeded successfully!')
    except Exception as e:
        print(f'❌ Subscription tier seeding failed: {str(e)}')
        db.session.rollback()
        raise


@click.command('seed-feature-flags')
@with_appcontext
def seed_feature_flags_command():
    """Seed feature flags from the catalog"""
    try:
        print("🔄 Seeding feature flags...")
        from .seeders.feature_flag_seeder import seed_feature_flags
        seed_feature_flags()
        print("✅ Feature flags seeded successfully!")
    except Exception as e:
        print(f"❌ Feature flag seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command('seed-app-settings')
@with_appcontext
def seed_app_settings_command():
    """Seed default app settings"""
    try:
        print("🔄 Seeding app settings...")
        from .seeders.app_settings_seeder import seed_app_settings
        seed_app_settings()
        print("✅ App settings seeded successfully!")
    except Exception as e:
        print(f"❌ App settings seeding failed: {str(e)}")
        db.session.rollback()
        raise

@click.command('seed-categories')
@with_appcontext
def seed_categories_command():
    """Seed ingredient categories"""
    try:
        print("🔧 Seeding categories...")
        from .models import Organization
        from .seeders.ingredient_category_seeder import seed_categories

        org = Organization.query.first()
        if not org:
            print("❌ No organization found. Run 'flask seed-production' first.")
            return

        seed_categories(organization_id=org.id)
        print("✅ Categories seeded successfully")
    except Exception as e:
        print(f'❌ Category seeding failed: {str(e)}')
        db.session.rollback()
        raise

@click.command('seed-product-categories')
@with_appcontext
def seed_product_categories_command():
    """Seed product categories, including 'Uncategorized'"""
    try:
        print("🔧 Seeding product categories...")
        from .seeders.product_category_seeder import seed_product_categories
        seed_product_categories()
        print("✅ Product categories seeded successfully")
    except Exception as e:
        print(f'❌ Product category seeding failed: {e}')
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

@click.command('clear-all-users')
@with_appcontext
def clear_all_users_command():
    """Clear all user data while preserving schema"""
    try:
        print("🚨 DANGER: This will clear ALL user data!")
        print("⚠️  This removes all users, organizations, and related data")
        print("✅ Schema (permissions, roles, tiers) will be preserved")

        confirmation = input("Type 'CLEAR ALL USERS' to confirm: ")
        if confirmation != 'CLEAR ALL USERS':
            print("❌ Operation cancelled")
            return

        from .models import (
            User, Organization, UserRoleAssignment, 
            UserStats, OrganizationStats
        )
        from .models.user_preferences import UserPreferences

        # Get organization IDs for bulk operations
        org_ids = [o.id for o in Organization.query.all()]
        user_ids = [u.id for u in User.query.all()]

        # Clear in proper dependency order to handle all PostgreSQL constraints
        print("🗑️  Clearing user role assignments...")
        if user_ids:
            db.session.execute(db.text("DELETE FROM user_role_assignment WHERE user_id = ANY(:user_ids)"), {"user_ids": user_ids})

        print("🗑️  Clearing user statistics...")
        if user_ids:
            db.session.execute(db.text("DELETE FROM user_stats WHERE user_id = ANY(:user_ids)"), {"user_ids": user_ids})

        print("🗑️  Clearing organization statistics...")
        if org_ids:
            db.session.execute(db.text("DELETE FROM organization_stats WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})

        print("🗑️  Clearing user preferences...")
        if user_ids:
            db.session.execute(db.text("DELETE FROM user_preferences WHERE user_id = ANY(:user_ids)"), {"user_ids": user_ids})

        # Clear organization-dependent tables that reference organization_id
        print("🗑️  Clearing ingredient categories...")
        if org_ids:
            db.session.execute(db.text("DELETE FROM ingredient_category WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})

        print("🗑️  Clearing custom unit mappings...")
        if org_ids:
            db.session.execute(db.text("DELETE FROM custom_unit_mapping WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})

        # Clear other organization-scoped data
        organization_tables = [
            'recipe', 'batch', 'inventory_item', 'inventory_history',
            'product', 'product_sku', 'product_variant', 'batch_inventory_log',
            'reservation', 'conversion_log'
        ]

        for table in organization_tables:
            print(f"🗑️  Clearing {table}...")
            try:
                if org_ids:
                    # Check if table exists and has organization_id column
                    result = db.session.execute(db.text("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name = :table_name 
                        AND column_name = 'organization_id'
                    """), {"table_name": table}).fetchone()

                    if result:
                        db.session.execute(db.text(f"DELETE FROM {table} WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})
                    else:
                        print(f"   ⚠️  {table} doesn't have organization_id column - skipping")
            except Exception as table_error:
                print(f"   ⚠️  Could not clear {table}: {table_error}")
                # Continue with other tables

        print("🗑️  Clearing all users...")
        user_count = len(user_ids)
        db.session.execute(db.text("DELETE FROM \"user\""))

        print("🗑️  Clearing all organizations...")
        org_count = len(org_ids)
        db.session.execute(db.text("DELETE FROM organization"))

        db.session.commit()

        print("✅ All user data cleared successfully!")
        print(f"   - Removed {user_count} users")
        print(f"   - Removed {org_count} organizations")
        print("🔄 Run 'flask init-production' to recreate default data")

    except Exception as e:
        print(f'❌ Error clearing user data: {str(e)}')
        db.session.rollback()
        raise

@click.command('clear-dev-users')
@with_appcontext
def clear_dev_users_command():
    """Clear only developer users"""
    try:
        print("🧹 Clearing developer users only...")
        print("👥 Customer users and organizations will be preserved")

        from .models import User, UserRoleAssignment
        from .models.user_preferences import UserPreferences

        # Show current developer users
        dev_users = User.query.filter_by(user_type='developer').all()
        if not dev_users:
            print("ℹ️  No developer users found")
            return

        print(f"📋 Found {len(dev_users)} developer users:")
        for user in dev_users:
            print(f"   - {user.username} ({user.email})")

        confirmation = input("Type 'CLEAR DEVS' to confirm: ")
        if confirmation != 'CLEAR DEVS':
            print("❌ Operation cancelled")
            return

        # Get developer user IDs for role assignment cleanup
        dev_user_ids = [user.id for user in dev_users]

        # Clear developer role assignments
        print("🗑️  Clearing developer role assignments...")
        assignments_deleted = UserRoleAssignment.query.filter(
            UserRoleAssignment.user_id.in_(dev_user_ids)
        ).delete(synchronize_session=False)

        # Clear developer user preferences  
        print("🗑️  Clearing developer user preferences...")
        prefs_deleted = UserPreferences.query.filter(
            UserPreferences.user_id.in_(dev_user_ids)
        ).delete(synchronize_session=False)

        # Clear developer users
        print("🗑️  Clearing developer users...")
        users_deleted = User.query.filter_by(user_type='developer').delete()

        db.session.commit()

        print("✅ Developer users cleared successfully!")
        print(f"   - Removed {users_deleted} developer users")
        print(f"   - Removed {assignments_deleted} role assignments")
        print(f"   - Removed {prefs_deleted} user preferences")
        print("🔄 Run 'flask seed-users' to recreate developer user")

    except Exception as e:
        print(f'❌ Error clearing developer users: {str(e)}')
        db.session.rollback()
        raise

@click.command('clear-customer-users')
@with_appcontext
def clear_customer_users_command():
    """Clear customer users and organizations while preserving developers and schema"""
    try:
        print("⚠️  This removes all CUSTOMER users and organizations")
        print("✅ Developer users will be preserved")
        print("✅ Schema (permissions, roles, tiers) will be preserved")

        confirmation = input("Type 'CLEAR CUSTOMER USERS' to confirm: ")
        if confirmation != 'CLEAR CUSTOMER USERS':
            print("❌ Operation cancelled")
            return

        from .models import User, Organization
        from .models.user_role_assignment import UserRoleAssignment
        from .models.statistics import UserStats, OrganizationStats
        from .models.user_preferences import UserPreferences

        # Get IDs for bulk operations
        customer_user_ids = [u.id for u in User.query.filter_by(user_type='customer').all()]
        org_ids = [o.id for o in Organization.query.all()]

        # Clear in proper dependency order to handle all PostgreSQL constraints
        print("🗑️  Clearing customer user role assignments...")
        if customer_user_ids:
            db.session.execute(db.text("DELETE FROM user_role_assignment WHERE user_id = ANY(:user_ids)"), {"user_ids": customer_user_ids})

        print("🗑️  Clearing customer user statistics...")
        if customer_user_ids:
            db.session.execute(db.text("DELETE FROM user_stats WHERE user_id = ANY(:user_ids)"), {"user_ids": customer_user_ids})

        print("🗑️  Clearing organization statistics...")
        if org_ids:
            db.session.execute(db.text("DELETE FROM organization_stats WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})

        print("🗑️  Clearing customer user preferences...")
        if customer_user_ids:
            db.session.execute(db.text("DELETE FROM user_preferences WHERE user_id = ANY(:user_ids)"), {"user_ids": customer_user_ids})

        # Clear organization-dependent tables that reference organization_id
        print("🗑️  Clearing ingredient categories...")
        if org_ids:
            db.session.execute(db.text("DELETE FROM ingredient_category WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})

        print("🗑️  Clearing custom unit mappings...")
        if org_ids:
            db.session.execute(db.text("DELETE FROM custom_unit_mapping WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})

        # Clear other organization-scoped data
        organization_tables = [
            'recipe', 'batch', 'inventory_item', 'inventory_history',
            'product', 'product_sku', 'product_variant', 'batch_inventory_log',
            'reservation', 'conversion_log'
        ]

        for table in organization_tables:
            print(f"🗑️  Clearing {table}...")
            try:
                if org_ids:
                    # Check if table exists and has organization_id column
                    result = db.session.execute(db.text("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name = :table_name 
                        AND column_name = 'organization_id'
                    """), {"table_name": table}).fetchone()

                    if result:
                        db.session.execute(db.text(f"DELETE FROM {table} WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})
                    else:
                        print(f"   ⚠️  {table} doesn't have organization_id column - skipping")
            except Exception as table_error:
                print(f"   ⚠️  Could not clear {table}: {table_error}")
                # Continue with other tables

        # Handle user-referenced columns by setting them to NULL (preserve data but remove user references)
        print("🗑️  Clearing user references in organization data...")
        user_reference_tables = [
            ('batch', ['created_by', 'updated_by', 'assigned_by', 'deleted_by']),
            ('recipe', ['created_by', 'updated_by', 'deleted_by']),
            ('inventory_item', ['created_by', 'updated_by', 'deleted_by']),
            ('inventory_history', ['created_by', 'updated_by']),
            ('product', ['created_by', 'updated_by', 'deleted_by']),
            ('product_sku', ['created_by', 'updated_by', 'deleted_by']),
            ('reservation', ['created_by', 'updated_by'])
        ]

        for table, columns in user_reference_tables:
            try:
                if customer_user_ids:
                    for column in columns:
                        # Check if column exists before trying to update it
                        result = db.session.execute(db.text("""
                            SELECT column_name FROM information_schema.columns 
                            WHERE table_name = :table_name 
                            AND column_name = :column_name
                        """), {"table_name": table, "column_name": column}).fetchone()

                        if result:
                            db.session.execute(db.text(f"UPDATE {table} SET {column} = NULL WHERE {column} = ANY(:user_ids)"), {"user_ids": customer_user_ids})
                            print(f"   ✅ Cleared {column} references in {table}")
                        else:
                            print(f"   ⚠️  Column {column} doesn't exist in {table} - skipping")
            except Exception as table_error:
                print(f"   ⚠️  Could not clear user references in {table}: {table_error}")
                # Continue with other tables

        # Clear all customer users
        print("🗑️  Clearing customer users...")
        db.session.execute(db.text("DELETE FROM \"user\" WHERE user_type = 'customer'"))

        # Clear all organizations
        print("🗑️  Clearing organizations...")
        db.session.execute(db.text("DELETE FROM organization"))

        # Commit all changes
        db.session.commit()
        print("✅ Customer users and organizations cleared successfully")

        # Summary
        remaining_users = User.query.count()
        remaining_orgs = Organization.query.count()
        print(f"\n📊 Summary:")
        print(f"Remaining users: {remaining_users} (should be developers only)")
        print(f"Remaining organizations: {remaining_orgs} (should be 0)")

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error clearing customer user data: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
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

        # Create only missing tables (safe operation)
        print("🏗️  Creating any missing tables...")
        existing_tables = set(inspect(db.engine).get_table_names())
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

@click.command('seed-test-data')
@with_appcontext
def seed_test_data_command():
    """Seed comprehensive test data for system testing"""
    try:
        print("🧪 Seeding test data...")
        from .models import Organization

        # Check if organizations exist
        orgs = Organization.query.all()
        if not orgs:
            print("❌ No organizations found! Run production seeding first.")
            return

        # Show available organizations
        print(f"\n📋 Available Organizations ({len(orgs)}):")
        for i, org in enumerate(orgs, 1):
            tier_info = f" (Tier: {org.tier.name})" if org.tier else " (No tier)"
            print(f"   {i}. {org.name}{tier_info}")

        # Get user selection
        while True:
            try:
                choice = input(f"\nSelect organization (1-{len(orgs)}) or press Enter for first: ").strip()

                if not choice:  # Default to first organization
                    selected_org = orgs[0]
                    break

                choice_num = int(choice)
                if 1 <= choice_num <= len(orgs):
                    selected_org = orgs[choice_num - 1]
                    break
                else:
                    print(f"❌ Please enter a number between 1 and {len(orgs)}")
            except ValueError:
                print("❌ Please enter a valid number")
            except KeyboardInterrupt:
                print("\n❌ Operation cancelled")
                return

        print(f"\n✅ Selected: {selected_org.name} (ID: {selected_org.id})")

        from .seeders import seed_test_data
        seed_test_data(organization_id=selected_org.id)
        print("✅ Test data seeded successfully!")

    except Exception as e:
        print(f'❌ Test data seeding failed: {str(e)}')
        import traceback
        traceback.print_exc()
        db.session.rollback()


@click.command('seed-global-inventory')
@with_appcontext
def seed_global_inventory_command():
    """Seed complete global inventory library (ingredients, containers, packaging, consumables)"""
    try:
        print("🔄 Seeding global inventory library...")
        from .seeders.seed_global_inventory_library import seed_global_inventory_library
        seed_global_inventory_library()
        print('✅ Global inventory library seeded successfully!')
    except Exception as e:
        print(f'❌ Global inventory seeding failed: {str(e)}')
        db.session.rollback()
        raise

# New command to generate container attributes
@click.command('generate-container-attributes')
@with_appcontext
def generate_container_attributes_command():
    """Generates JSON files for container attributes (style, type, color, material)"""
    try:
        print("✨ Generating container attribute JSON files...")
        from .seeders.container_attribute_generator import generate_attributes
        generate_attributes()
        print("✅ Container attribute JSON files generated successfully!")
    except Exception as e:
        print(f"❌ Error generating container attributes: {str(e)}")
        db.session.rollback()
        raise


@click.command('dispatch-domain-events')
@click.option('--poll-interval', default=5.0, show_default=True, help='Seconds to wait between polls when idle.')
@click.option('--batch-size', default=100, show_default=True, type=int, help='Maximum events to process per batch.')
@click.option('--once', is_flag=True, help='Process a single batch instead of running continuously.')
@with_appcontext
def dispatch_domain_events_command(poll_interval: float, batch_size: int, once: bool):
    """Run the asynchronous dispatcher that delivers pending domain events."""
    from app.services.domain_event_dispatcher import DomainEventDispatcher

    dispatcher = DomainEventDispatcher(batch_size=batch_size)

    if once:
        metrics = dispatcher.dispatch_pending_events()
        click.echo(
            f"Processed {metrics['processed']} events ({metrics['succeeded']} succeeded, {metrics['failed']} failed)."
        )
    else:
        click.echo(
            f"Starting domain event dispatcher (batch_size={batch_size}, poll_interval={poll_interval}s)..."
        )
        dispatcher.run_forever(poll_interval=poll_interval)


@click.command('minify-static')
@with_appcontext
def minify_static_command():
    """Generate minified .min.js/.min.css assets under the static folder."""
    try:
        from rcssmin import cssmin
        from rjsmin import jsmin
    except ImportError as exc:
        raise click.ClickException(
            "Missing minifier dependency. Install `rjsmin` and `rcssmin` to run this command."
        ) from exc

    static_folder = Path(current_app.static_folder or "static")
    if not static_folder.is_dir():
        raise click.ClickException(f"Static folder not found: {static_folder}")

    processed = 0
    written = 0
    unchanged = 0
    failed = 0

    for source_path in sorted(static_folder.rglob("*")):
        if not source_path.is_file():
            continue
        suffix = source_path.suffix.lower()
        if suffix not in {".js", ".css"}:
            continue
        if source_path.name.endswith(f".min{suffix}"):
            continue
        if suffix == ".js" and source_path.name.endswith(".config.js"):
            # Build-time config files are not served as browser assets.
            continue

        processed += 1
        target_path = source_path.with_name(f"{source_path.stem}.min{suffix}")

        try:
            source_text = source_path.read_text(encoding="utf-8")
            minified_text = jsmin(source_text) if suffix == ".js" else cssmin(source_text)
            if minified_text and not minified_text.endswith("\n"):
                minified_text += "\n"

            if target_path.exists():
                existing_text = target_path.read_text(encoding="utf-8")
                if existing_text == minified_text:
                    unchanged += 1
                    continue

            target_path.write_text(minified_text, encoding="utf-8")
            written += 1
            click.echo(
                f"minified: {source_path.relative_to(static_folder).as_posix()} "
                f"-> {target_path.relative_to(static_folder).as_posix()}"
            )
        except Exception as exc:
            failed += 1
            click.echo(f"failed: {source_path.relative_to(static_folder).as_posix()} ({exc})")

    click.echo(
        f"Static minification complete. processed={processed}, written={written}, "
        f"unchanged={unchanged}, failed={failed}"
    )
    if failed:
        raise click.ClickException("One or more static assets failed to minify.")


def register_commands(app):
    """Register CLI commands"""
    # Database initialization
    app.cli.add_command(create_app_command)
    app.cli.add_command(sync_schema_command)

    # One-time initialization (fresh installs only)
    app.cli.add_command(init_production_command)

    # Data clearing commands (DANGER ZONE)
    app.cli.add_command(clear_all_users_command)
    app.cli.add_command(clear_dev_users_command)
    app.cli.add_command(clear_customer_users_command)

    # Individual seeders
    app.cli.add_command(seed_users_command)
    app.cli.add_command(seed_permissions_command)
    app.cli.add_command(seed_organizations_command)
    app.cli.add_command(seed_units_command)
    app.cli.add_command(seed_sub_tiers_command)
    app.cli.add_command(seed_feature_flags_command)
    app.cli.add_command(seed_app_settings_command)
    app.cli.add_command(seed_categories_command)
    app.cli.add_command(seed_product_categories_command) # Added new command
    app.cli.add_command(seed_test_data_command)
    app.cli.add_command(seed_permission_categories_command)
    app.cli.add_command(seed_global_inventory_command)
    app.cli.add_command(generate_container_attributes_command)

    # Production maintenance commands
    app.cli.add_command(update_permissions_command)
    app.cli.add_command(update_addons_command)
    app.cli.add_command(update_subscription_tiers_command)
    app.cli.add_command(activate_users)
    app.cli.add_command(dispatch_domain_events_command)
    app.cli.add_command(minify_static_command)