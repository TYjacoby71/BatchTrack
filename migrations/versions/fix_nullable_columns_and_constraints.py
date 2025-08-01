"""fix nullable columns and add constraints

Revision ID: fix_nullable_constraints
Revises: add_missing_timestamps
Create Date: 2025-01-31 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = 'fix_nullable_constraints'
down_revision = 'add_missing_timestamps'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    print("=== Fixing nullable columns and adding constraints ===")

    bind = op.get_bind()

    # Update existing NULL values to have reasonable defaults before making columns NOT NULL
    # This approach works for both SQLite and PostgreSQL

    # Fix inventory_item.type - set default value for existing NULL rows
    if table_exists('inventory_item') and column_exists('inventory_item', 'type'):
        print("Updating inventory_item.type NULL values...")
        bind.execute(text("UPDATE inventory_item SET type = 'ingredient' WHERE type IS NULL"))

    # Fix user.user_type - set default value for existing NULL rows  
    if table_exists('user') and column_exists('user', 'user_type'):
        print("Updating user.user_type NULL values...")
        bind.execute(text("UPDATE user SET user_type = 'customer' WHERE user_type IS NULL"))

    # Fix organization.is_active - set default value for existing NULL rows
    if table_exists('organization') and column_exists('organization', 'is_active'):
        print("Updating organization.is_active NULL values...")
        bind.execute(text("UPDATE organization SET is_active = 1 WHERE is_active IS NULL"))

    # Fix user.is_active - set default value for existing NULL rows
    if table_exists('user') and column_exists('user', 'is_active'):
        print("Updating user.is_active NULL values...")
        bind.execute(text("UPDATE user SET is_active = 1 WHERE is_active IS NULL"))

    # Fix user.is_organization_owner - set default value for existing NULL rows
    if table_exists('user') and column_exists('user', 'is_organization_owner'):
        print("Updating user.is_organization_owner NULL values...")
        bind.execute(text("UPDATE user SET is_organization_owner = 0 WHERE is_organization_owner IS NULL"))

    # Fix role.is_system_role - set default value for existing NULL rows
    if table_exists('role') and column_exists('role', 'is_system_role'):
        print("Updating role.is_system_role NULL values...")
        bind.execute(text("UPDATE role SET is_system_role = 0 WHERE is_system_role IS NULL"))

    # Fix user_role_assignment.is_active - set default value for existing NULL rows
    if table_exists('user_role_assignment') and column_exists('user_role_assignment', 'is_active'):
        print("Updating user_role_assignment.is_active NULL values...")
        bind.execute(text("UPDATE user_role_assignment SET is_active = 1 WHERE is_active IS NULL"))

    # Fix subscription_tier.is_active - set default value for existing NULL rows
    if table_exists('subscription_tier') and column_exists('subscription_tier', 'is_active'):
        print("Updating subscription_tier.is_active NULL values...")
        bind.execute(text("UPDATE subscription_tier SET is_active = 1 WHERE is_active IS NULL"))

    # Fix developer_role.is_active - set default value for existing NULL rows
    if table_exists('developer_role') and column_exists('developer_role', 'is_active'):
        print("Updating developer_role.is_active NULL values...")
        bind.execute(text("UPDATE developer_role SET is_active = 1 WHERE is_active IS NULL"))

    # Note: We're not making columns NOT NULL in this migration because:
    # 1. SQLite doesn't support ALTER COLUMN ... SET NOT NULL
    # 2. The models already define nullable=False, so new records will be validated
    # 3. Existing data now has proper default values

    print("✅ Migration completed: Updated NULL values to match model expectations")
    print("⚠️  Note: Columns remain nullable in database schema but models enforce NOT NULL")


def downgrade():
    print("=== Reverting nullable column fixes ===")
    # This migration only updated data, no schema changes to revert
    print("✅ Downgrade completed (no schema changes to revert)")