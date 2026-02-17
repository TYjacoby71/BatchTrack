"""Danger-zone commands for destructive user/org data operations."""

import click
from flask.cli import with_appcontext

from ...extensions import db


@click.command("clear-all-users")
@with_appcontext
def clear_all_users_command():
    """Clear all user data while preserving schema."""
    try:
        print("🚨 DANGER: This will clear ALL user data!")
        print("⚠️  This removes all users, organizations, and related data")
        print("✅ Schema (permissions, roles, tiers) will be preserved")

        confirmation = input("Type 'CLEAR ALL USERS' to confirm: ")
        if confirmation != "CLEAR ALL USERS":
            print("❌ Operation cancelled")
            return

        from ...models import Organization, User

        org_ids = [o.id for o in Organization.query.all()]
        user_ids = [u.id for u in User.query.all()]

        print("🗑️  Clearing user role assignments...")
        if user_ids:
            db.session.execute(
                db.text(
                    "DELETE FROM user_role_assignment WHERE user_id = ANY(:user_ids)"
                ),
                {"user_ids": user_ids},
            )

        print("🗑️  Clearing user statistics...")
        if user_ids:
            db.session.execute(
                db.text("DELETE FROM user_stats WHERE user_id = ANY(:user_ids)"),
                {"user_ids": user_ids},
            )

        print("🗑️  Clearing organization statistics...")
        if org_ids:
            db.session.execute(
                db.text(
                    "DELETE FROM organization_stats WHERE organization_id = ANY(:org_ids)"
                ),
                {"org_ids": org_ids},
            )

        print("🗑️  Clearing user preferences...")
        if user_ids:
            db.session.execute(
                db.text("DELETE FROM user_preferences WHERE user_id = ANY(:user_ids)"),
                {"user_ids": user_ids},
            )

        print("🗑️  Clearing ingredient categories...")
        if org_ids:
            db.session.execute(
                db.text(
                    "DELETE FROM ingredient_category WHERE organization_id = ANY(:org_ids)"
                ),
                {"org_ids": org_ids},
            )

        print("🗑️  Clearing custom unit mappings...")
        if org_ids:
            db.session.execute(
                db.text(
                    "DELETE FROM custom_unit_mapping WHERE organization_id = ANY(:org_ids)"
                ),
                {"org_ids": org_ids},
            )

        organization_tables = [
            "recipe",
            "batch",
            "inventory_item",
            "inventory_history",
            "product",
            "product_sku",
            "product_variant",
            "batch_inventory_log",
            "reservation",
            "conversion_log",
        ]

        for table in organization_tables:
            print(f"🗑️  Clearing {table}...")
            try:
                if org_ids:
                    result = db.session.execute(
                        db.text("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = :table_name
                        AND column_name = 'organization_id'
                    """),
                        {"table_name": table},
                    ).fetchone()

                    if result:
                        db.session.execute(
                            db.text(
                                f"DELETE FROM {table} WHERE organization_id = ANY(:org_ids)"
                            ),
                            {"org_ids": org_ids},
                        )
                    else:
                        print(
                            f"   ⚠️  {table} doesn't have organization_id column - skipping"
                        )
            except Exception as table_error:
                print(f"   ⚠️  Could not clear {table}: {table_error}")

        print("🗑️  Clearing all users...")
        user_count = len(user_ids)
        db.session.execute(db.text('DELETE FROM "user"'))

        print("🗑️  Clearing all organizations...")
        org_count = len(org_ids)
        db.session.execute(db.text("DELETE FROM organization"))

        db.session.commit()

        print("✅ All user data cleared successfully!")
        print(f"   - Removed {user_count} users")
        print(f"   - Removed {org_count} organizations")
        print("🔄 Run 'flask init-production' to recreate default data")

    except Exception as e:
        print(f"❌ Error clearing user data: {str(e)}")
        db.session.rollback()
        raise


@click.command("clear-dev-users")
@with_appcontext
def clear_dev_users_command():
    """Clear only developer users."""
    try:
        print("🧹 Clearing developer users only...")
        print("👥 Customer users and organizations will be preserved")

        from ...models import User, UserRoleAssignment
        from ...models.user_preferences import UserPreferences

        dev_users = User.query.filter_by(user_type="developer").all()
        if not dev_users:
            print("ℹ️  No developer users found")
            return

        print(f"📋 Found {len(dev_users)} developer users:")
        for user in dev_users:
            print(f"   - {user.username} ({user.email})")

        confirmation = input("Type 'CLEAR DEVS' to confirm: ")
        if confirmation != "CLEAR DEVS":
            print("❌ Operation cancelled")
            return

        dev_user_ids = [user.id for user in dev_users]

        print("🗑️  Clearing developer role assignments...")
        assignments_deleted = UserRoleAssignment.query.filter(
            UserRoleAssignment.user_id.in_(dev_user_ids)
        ).delete(synchronize_session=False)

        print("🗑️  Clearing developer user preferences...")
        prefs_deleted = UserPreferences.query.filter(
            UserPreferences.user_id.in_(dev_user_ids)
        ).delete(synchronize_session=False)

        print("🗑️  Clearing developer users...")
        users_deleted = User.query.filter_by(user_type="developer").delete()

        db.session.commit()

        print("✅ Developer users cleared successfully!")
        print(f"   - Removed {users_deleted} developer users")
        print(f"   - Removed {assignments_deleted} role assignments")
        print(f"   - Removed {prefs_deleted} user preferences")
        print("🔄 Run 'flask seed-users' to recreate developer user")

    except Exception as e:
        print(f"❌ Error clearing developer users: {str(e)}")
        db.session.rollback()
        raise


@click.command("clear-customer-users")
@with_appcontext
def clear_customer_users_command():
    """Clear customer users and organizations while preserving developers and schema."""
    try:
        print("⚠️  This removes all CUSTOMER users and organizations")
        print("✅ Developer users will be preserved")
        print("✅ Schema (permissions, roles, tiers) will be preserved")

        confirmation = input("Type 'CLEAR CUSTOMER USERS' to confirm: ")
        if confirmation != "CLEAR CUSTOMER USERS":
            print("❌ Operation cancelled")
            return

        from ...models import Organization, User

        customer_user_ids = [
            u.id for u in User.query.filter_by(user_type="customer").all()
        ]
        org_ids = [o.id for o in Organization.query.all()]

        print("🗑️  Clearing customer user role assignments...")
        if customer_user_ids:
            db.session.execute(
                db.text(
                    "DELETE FROM user_role_assignment WHERE user_id = ANY(:user_ids)"
                ),
                {"user_ids": customer_user_ids},
            )

        print("🗑️  Clearing customer user statistics...")
        if customer_user_ids:
            db.session.execute(
                db.text("DELETE FROM user_stats WHERE user_id = ANY(:user_ids)"),
                {"user_ids": customer_user_ids},
            )

        print("🗑️  Clearing organization statistics...")
        if org_ids:
            db.session.execute(
                db.text(
                    "DELETE FROM organization_stats WHERE organization_id = ANY(:org_ids)"
                ),
                {"org_ids": org_ids},
            )

        print("🗑️  Clearing customer user preferences...")
        if customer_user_ids:
            db.session.execute(
                db.text("DELETE FROM user_preferences WHERE user_id = ANY(:user_ids)"),
                {"user_ids": customer_user_ids},
            )

        print("🗑️  Clearing ingredient categories...")
        if org_ids:
            db.session.execute(
                db.text(
                    "DELETE FROM ingredient_category WHERE organization_id = ANY(:org_ids)"
                ),
                {"org_ids": org_ids},
            )

        print("🗑️  Clearing custom unit mappings...")
        if org_ids:
            db.session.execute(
                db.text(
                    "DELETE FROM custom_unit_mapping WHERE organization_id = ANY(:org_ids)"
                ),
                {"org_ids": org_ids},
            )

        organization_tables = [
            "recipe",
            "batch",
            "inventory_item",
            "inventory_history",
            "product",
            "product_sku",
            "product_variant",
            "batch_inventory_log",
            "reservation",
            "conversion_log",
        ]

        for table in organization_tables:
            print(f"🗑️  Clearing {table}...")
            try:
                if org_ids:
                    result = db.session.execute(
                        db.text("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = :table_name
                        AND column_name = 'organization_id'
                    """),
                        {"table_name": table},
                    ).fetchone()

                    if result:
                        db.session.execute(
                            db.text(
                                f"DELETE FROM {table} WHERE organization_id = ANY(:org_ids)"
                            ),
                            {"org_ids": org_ids},
                        )
                    else:
                        print(
                            f"   ⚠️  {table} doesn't have organization_id column - skipping"
                        )
            except Exception as table_error:
                print(f"   ⚠️  Could not clear {table}: {table_error}")

        print("🗑️  Clearing user references in organization data...")
        user_reference_tables = [
            ("batch", ["created_by", "updated_by", "assigned_by", "deleted_by"]),
            ("recipe", ["created_by", "updated_by", "deleted_by"]),
            ("inventory_item", ["created_by", "updated_by", "deleted_by"]),
            ("inventory_history", ["created_by", "updated_by"]),
            ("product", ["created_by", "updated_by", "deleted_by"]),
            ("product_sku", ["created_by", "updated_by", "deleted_by"]),
            ("reservation", ["created_by", "updated_by"]),
        ]

        for table, columns in user_reference_tables:
            try:
                if customer_user_ids:
                    for column in columns:
                        result = db.session.execute(
                            db.text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = :table_name
                            AND column_name = :column_name
                        """),
                            {"table_name": table, "column_name": column},
                        ).fetchone()

                        if result:
                            db.session.execute(
                                db.text(
                                    f"UPDATE {table} SET {column} = NULL WHERE {column} = ANY(:user_ids)"
                                ),
                                {"user_ids": customer_user_ids},
                            )
                            print(f"   ✅ Cleared {column} references in {table}")
                        else:
                            print(
                                f"   ⚠️  Column {column} doesn't exist in {table} - skipping"
                            )
            except Exception as table_error:
                print(
                    f"   ⚠️  Could not clear user references in {table}: {table_error}"
                )

        print("🗑️  Clearing customer users...")
        db.session.execute(db.text("DELETE FROM \"user\" WHERE user_type = 'customer'"))

        print("🗑️  Clearing organizations...")
        db.session.execute(db.text("DELETE FROM organization"))

        db.session.commit()
        print("✅ Customer users and organizations cleared successfully")

        remaining_users = User.query.count()
        remaining_orgs = Organization.query.count()
        print("\n📊 Summary:")
        print(f"Remaining users: {remaining_users} (should be developers only)")
        print(f"Remaining organizations: {remaining_orgs} (should be 0)")

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error clearing customer user data: {e}")
        import traceback

        print(f"Full traceback: {traceback.format_exc()}")
        raise


DESTRUCTIVE_COMMANDS = [
    clear_all_users_command,
    clear_dev_users_command,
    clear_customer_users_command,
]
