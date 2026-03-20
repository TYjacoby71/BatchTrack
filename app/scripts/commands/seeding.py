"""Seeder and initialization CLI commands grouped by process stage."""

import logging

import click
from flask.cli import with_appcontext
from sqlalchemy import inspect

from ...extensions import db
from ...models import Organization, User
from ...seeders import (
    seed_app_settings,
    seed_feature_flags,
    seed_subscriptions,
    seed_units,
)
from ...seeders.addon_seeder import seed_addons
from ...seeders.consolidated_permission_seeder import seed_consolidated_permissions
from ...seeders.user_seeder import seed_users_and_organization

logger = logging.getLogger(__name__)


@click.command("activate-users")
@with_appcontext
def activate_users():
    """Activate all inactive users."""
    try:
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
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:36",
            exc_info=True,
        )
        print(f"❌ Error activating users: {str(e)}")
        raise


@click.command("init-production")
@with_appcontext
def init_production_command():
    """Seed production database with essential data (run after migrations)."""
    try:
        print("🚀 BatchTrack Production Seeding Starting...")
        print("⚠️  Assumes database schema is already migrated (flask db upgrade)")

        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        required_tables = [
            "permission",
            "subscription_tier",
            "unit",
            "organization",
            "user",
        ]
        missing_tables = [t for t in required_tables if t not in tables]

        if missing_tables:
            print(f"❌ Missing required tables: {missing_tables}")
            print("   Run 'flask db upgrade' first to create database schema")
            return

        print("=== Step 1: System foundations (Organization Independent) ===")

        try:
            seed_consolidated_permissions()
            print("✅ Permissions, organization roles, and developer roles seeded")
        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:70",
                exc_info=True,
            )
            print(f"⚠️  Permission seeding issue: {e}")
            print("   Continuing with remaining steps...")

        try:
            seed_subscriptions()
            print("✅ Subscription tiers seeded")
        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:77",
                exc_info=True,
            )
            print(f"⚠️  Subscription seeding issue: {e}")
            print("   Continuing with remaining steps...")

        try:
            seed_feature_flags()
            print("✅ Feature flags seeded")
        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:84",
                exc_info=True,
            )
            print(f"⚠️  Feature flag seeding issue: {e}")
            print("   Continuing with remaining steps...")

        try:
            seed_app_settings()
            print("✅ App settings seeded")
        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:91",
                exc_info=True,
            )
            print(f"⚠️  App settings seeding issue: {e}")
            print("   Continuing with remaining steps...")

        try:
            seed_addons()
            print("✅ Add-ons seeded")
            try:
                from ...seeders.addon_seeder import backfill_addon_permissions

                backfill_addon_permissions()
            except Exception as e:
                logger.warning(
                    "Suppressed exception fallback at app/scripts/commands/seeding.py:102",
                    exc_info=True,
                )
                print(f"⚠️  Add-on permission backfill issue: {e}")
        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:104",
                exc_info=True,
            )
            print(f"⚠️  Add-on seeding issue: {e}")
            print("   Continuing with remaining steps...")

        try:
            seed_units()
            print("✅ Units seeded")
        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:111",
                exc_info=True,
            )
            print(f"⚠️  Unit seeding issue: {e}")
            print("   Continuing with remaining steps...")

        print("=== Step 2: Organization-dependent setup ===")
        print("ℹ️  Developer roles should now exist for user assignment...")
        try:
            seed_users_and_organization()
            print("✅ Organization and users seeded")
        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:120",
                exc_info=True,
            )
            print(f"⚠️  User/organization seeding issue: {e}")
            print("   Continuing with remaining steps...")

        print("=== Step 3: Organization-specific data ===")
        print("   Categories will be created by global inventory library seeding...")

        try:
            from ...seeders.product_category_seeder import seed_product_categories

            seed_product_categories()
            print("✅ Product categories seeded")
        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:132",
                exc_info=True,
            )
            print(f"⚠️  Product category seeding issue: {e}")

        try:
            from ...seeders.seed_global_inventory_library import (
                seed_global_inventory_library,
            )

            seed_global_inventory_library()
            print("✅ Global inventory library seeded")
        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:142",
                exc_info=True,
            )
            print(f"⚠️  Global inventory library seeding issue: {e}")

        print("\n📊 Production Seeding Summary:")
        try:
            try:
                db.session.rollback()
            except Exception:
                logger.warning(
                    "Suppressed exception fallback at app/scripts/commands/seeding.py:149",
                    exc_info=True,
                )
                pass
            from ...models import (
                Addon,
                DeveloperPermission,
                DeveloperRole,
                GlobalItem,
                IngredientCategory,
                Organization,
                Permission,
                ProductCategory,
                Role,
                SubscriptionTier,
                Unit,
                User,
            )

            org_permissions = Permission.query.filter_by(is_active=True).count()
            dev_permissions = DeveloperPermission.query.filter_by(
                is_active=True
            ).count()
            dev_roles = DeveloperRole.query.filter_by(is_active=True).count()
            Role.query.filter_by(is_system_role=True).count()
            sub_tiers = SubscriptionTier.query.count()
            addons = Addon.query.filter_by(is_active=True).count()
            units = Unit.query.count()

            organizations = Organization.query.count()
            total_users = User.query.count()
            dev_users = User.query.filter_by(user_type="developer").count()
            customer_users = User.query.filter_by(user_type="customer").count()

            ingredient_categories = IngredientCategory.query.count()
            product_categories = ProductCategory.query.count()
            ingredients_count = GlobalItem.query.filter_by(
                item_type="ingredient"
            ).count()
            containers_count = GlobalItem.query.filter_by(item_type="container").count()
            packaging_count = GlobalItem.query.filter_by(item_type="packaging").count()
            consumables_count = GlobalItem.query.filter_by(
                item_type="consumable"
            ).count()
            total_global_items = GlobalItem.query.count()

            print(
                f"  System:     {org_permissions} org perms, {dev_permissions} dev perms, {dev_roles} dev roles"
            )
            print(f"  Platform:   {sub_tiers} tiers, {addons} addons, {units} units")
            print(
                f"  Users:      {organizations} orgs, {total_users} users ({dev_users} dev, {customer_users} customer)"
            )
            print(
                f"  Catalogs:   {ingredient_categories} ingredient cats, {product_categories} product cats"
            )
            print(
                "  Library:    "
                f"{total_global_items} global items "
                f"({ingredients_count} ingredients, {containers_count} containers, "
                f"{packaging_count} packaging, {consumables_count} consumables)"
            )

            print("\n✅ Production seeding complete!")
            print("🔒 Login: admin/admin (CHANGE IMMEDIATELY)")
            print("📝 Note: This command can be run multiple times safely")

        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/scripts/commands/seeding.py:214",
                exc_info=True,
            )
            print(f"   - Status check failed: {e}")

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:217",
            exc_info=True,
        )
        print(f"❌ Production seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("seed-users")
@with_appcontext
def seed_users_command():
    """Seed users and organization."""
    try:
        print("🔄 Seeding users and organization...")
        seed_users_and_organization()
        print("✅ Users and organization seeded successfully!")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:231",
            exc_info=True,
        )
        print(f"❌ User seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("seed-permissions")
@with_appcontext
def seed_permissions_command():
    """Seed consolidated permissions."""
    try:
        print("🔄 Seeding permissions...")
        seed_consolidated_permissions()
        print("✅ Permissions seeded successfully!")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:245",
            exc_info=True,
        )
        print(f"❌ Permission seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("seed-organizations")
@with_appcontext
def seed_organizations_command():
    """Seed organizations (part of user seeding)."""
    try:
        print("🔄 Seeding organizations...")
        seed_users_and_organization()
        print("✅ Organizations seeded successfully!")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:259",
            exc_info=True,
        )
        print(f"❌ Organization seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("seed-units")
@with_appcontext
def seed_units_command():
    """Seed standard system units."""
    try:
        print("🔧 Seeding standard units...")

        inspector = inspect(db.engine)
        if "unit" not in inspector.get_table_names():
            print("❌ Unit table doesn't exist. Run 'flask db upgrade' first.")
            return

        columns = [col["name"] for col in inspector.get_columns("unit")]
        required_cols = [
            "id",
            "name",
            "symbol",
            "unit_type",
            "base_unit",
            "conversion_factor",
        ]
        missing_cols = [col for col in required_cols if col not in columns]
        if missing_cols:
            print(f"❌ Missing required columns in unit table: {missing_cols}")
            return

        has_timestamps = "created_at" in columns and "updated_at" in columns
        print(
            f"ℹ️  Unit table timestamp columns: {'✅ Present' if has_timestamps else '❌ Missing'}"
        )

        seed_units()
        print("✅ Units seeded successfully")

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:299",
            exc_info=True,
        )
        print(f"❌ Unit seeding failed: {str(e)}")
        import traceback

        traceback.print_exc()
        raise


@click.command("seed-sub-tiers")
@with_appcontext
def seed_sub_tiers_command():
    """Seed subscription tiers."""
    try:
        print("🔄 Seeding subscription tiers...")
        from ...seeders.subscription_seeder import seed_subscription_tiers

        seed_subscription_tiers()
        print("✅ Subscription tiers seeded successfully!")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:317",
            exc_info=True,
        )
        print(f"❌ Subscription tier seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("seed-feature-flags")
@with_appcontext
def seed_feature_flags_command():
    """Seed feature flags from the catalog."""
    try:
        print("🔄 Seeding feature flags...")
        seed_feature_flags()
        print("✅ Feature flags seeded successfully!")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:331",
            exc_info=True,
        )
        print(f"❌ Feature flag seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("seed-app-settings")
@with_appcontext
def seed_app_settings_command():
    """Seed default app settings."""
    try:
        print("🔄 Seeding app settings...")
        seed_app_settings()
        print("✅ App settings seeded successfully!")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:345",
            exc_info=True,
        )
        print(f"❌ App settings seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("seed-categories")
@with_appcontext
def seed_categories_command():
    """Seed ingredient categories."""
    try:
        print("🔧 Seeding categories...")
        from ...seeders.ingredient_category_seeder import seed_categories

        org = Organization.query.first()
        if not org:
            print("❌ No organization found. Run 'flask seed-production' first.")
            return

        seed_categories(organization_id=org.id)
        print("✅ Categories seeded successfully")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:366",
            exc_info=True,
        )
        print(f"❌ Category seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("seed-product-categories")
@with_appcontext
def seed_product_categories_command():
    """Seed product categories, including 'Uncategorized'."""
    try:
        print("🔧 Seeding product categories...")
        from ...seeders.product_category_seeder import seed_product_categories

        seed_product_categories()
        print("✅ Product categories seeded successfully")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:382",
            exc_info=True,
        )
        print(f"❌ Product category seeding failed: {e}")
        raise


@click.command("seed-permission-categories")
@click.option(
    "--category",
    help="Specific permission category to seed (app, organization, system, developer)",
)
@with_appcontext
def seed_permission_categories_command(category):
    """Seed permissions by category."""
    try:
        if category:
            print(f"🔄 Seeding {category} permission category...")
        else:
            print("🔄 Seeding all permission categories...")

        seed_consolidated_permissions()

        if category:
            print(f"✅ {category} permission category seeded successfully!")
        else:
            print("✅ All permission categories seeded successfully!")

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:408",
            exc_info=True,
        )
        print(f"❌ Permission category seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("seed-test-data")
@with_appcontext
def seed_test_data_command():
    """Seed comprehensive test data for system testing."""
    try:
        print("🧪 Seeding test data...")

        orgs = Organization.query.all()
        if not orgs:
            print("❌ No organizations found! Run production seeding first.")
            return

        print(f"\n📋 Available Organizations ({len(orgs)}):")
        for i, org in enumerate(orgs, 1):
            tier_info = f" (Tier: {org.tier.name})" if org.tier else " (No tier)"
            print(f"   {i}. {org.name}{tier_info}")

        while True:
            try:
                choice = input(
                    f"\nSelect organization (1-{len(orgs)}) or press Enter for first: "
                ).strip()

                if not choice:
                    selected_org = orgs[0]
                    break

                choice_num = int(choice)
                if 1 <= choice_num <= len(orgs):
                    selected_org = orgs[choice_num - 1]
                    break
                print(f"❌ Please enter a number between 1 and {len(orgs)}")
            except ValueError:
                print("❌ Please enter a valid number")
            except KeyboardInterrupt:
                print("\n❌ Operation cancelled")
                return

        print(f"\n✅ Selected: {selected_org.name} (ID: {selected_org.id})")

        from ...seeders import seed_test_data

        seed_test_data(organization_id=selected_org.id)
        print("✅ Test data seeded successfully!")

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:459",
            exc_info=True,
        )
        print(f"❌ Test data seeding failed: {str(e)}")
        import traceback

        traceback.print_exc()
        db.session.rollback()


@click.command("seed-global-inventory")
@with_appcontext
def seed_global_inventory_command():
    """Seed complete global inventory library (ingredients, containers, packaging, consumables)."""
    try:
        print("🔄 Seeding global inventory library...")
        from ...seeders.seed_global_inventory_library import (
            seed_global_inventory_library,
        )

        seed_global_inventory_library()
        print("✅ Global inventory library seeded successfully!")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:479",
            exc_info=True,
        )
        print(f"❌ Global inventory seeding failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("generate-container-attributes")
@with_appcontext
def generate_container_attributes_command():
    """Generate JSON files for container attributes (style, type, color, material)."""
    try:
        print("✨ Generating container attribute JSON files...")
        from ...seeders.container_attribute_generator import generate_attributes

        generate_attributes()
        print("✅ Container attribute JSON files generated successfully!")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/scripts/commands/seeding.py:495",
            exc_info=True,
        )
        print(f"❌ Error generating container attributes: {str(e)}")
        db.session.rollback()
        raise


BOOTSTRAP_COMMANDS = [init_production_command]

INDIVIDUAL_SEED_COMMANDS = [
    seed_users_command,
    seed_permissions_command,
    seed_organizations_command,
    seed_units_command,
    seed_sub_tiers_command,
    seed_feature_flags_command,
    seed_app_settings_command,
    seed_categories_command,
    seed_product_categories_command,
    seed_permission_categories_command,
    seed_test_data_command,
    seed_global_inventory_command,
    generate_container_attributes_command,
]

RECOVERY_COMMANDS = [activate_users]

SEEDING_COMMANDS = BOOTSTRAP_COMMANDS + INDIVIDUAL_SEED_COMMANDS + RECOVERY_COMMANDS
