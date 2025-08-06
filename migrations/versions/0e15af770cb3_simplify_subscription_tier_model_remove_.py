"""simplify subscription tier model - remove billing fields

Revision ID: 0e15af770cb3
Revises: a1b2c3d4e5f6789012345678901234ab
Create Date: 2025-08-06 00:21:44.088211

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0e15af770cb3'
down_revision = 'a1b2c3d4e5f6789012345678901234ab'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    def table_exists(table_name):
        """Check if a table exists"""
        try:
            return table_name in inspector.get_table_names()
        except Exception:
            return False

    print("=== Simplifying subscription tier model - removing billing fields ===")

    # Remove timestamp columns from developer_permission if they exist
    if table_exists('developer_permission'):
        print("   Checking developer_permission table...")
        with op.batch_alter_table('developer_permission', schema=None) as batch_op:
            if column_exists('developer_permission', 'updated_at'):
                print("   Dropping developer_permission.updated_at")
                batch_op.drop_column('updated_at')
            else:
                print("   ⚠️  developer_permission.updated_at does not exist - skipping")

            if column_exists('developer_permission', 'created_at'):
                print("   Dropping developer_permission.created_at")
                batch_op.drop_column('created_at')
            else:
                print("   ⚠️  developer_permission.created_at does not exist - skipping")
    else:
        print("   ⚠️  developer_permission table does not exist - skipping")

    # Remove timestamp columns from developer_role if they exist  
    if table_exists('developer_role'):
        print("   Checking developer_role table...")
        with op.batch_alter_table('developer_role', schema=None) as batch_op:
            if column_exists('developer_role', 'updated_at'):
                print("   Dropping developer_role.updated_at")
                batch_op.drop_column('updated_at')
            else:
                print("   ⚠️  developer_role.updated_at does not exist - skipping")

            if column_exists('developer_role', 'created_at'):
                print("   Dropping developer_role.created_at")
                batch_op.drop_column('created_at')
            else:
                print("   ⚠️  developer_role.created_at does not exist - skipping")
    else:
        print("   ⚠️  developer_role table does not exist - skipping")

    # Remove billing columns from subscription_tier if they exist
    if table_exists('subscription_tier'):
        print("   Checking subscription_tier table...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            if column_exists('subscription_tier', 'whop_plan_id'):
                print("   Dropping subscription_tier.whop_plan_id")
                batch_op.drop_column('whop_plan_id')
            else:
                print("   ⚠️  subscription_tier.whop_plan_id does not exist - skipping")

            if column_exists('subscription_tier', 'stripe_price_id'):
                print("   Dropping subscription_tier.stripe_price_id")
                batch_op.drop_column('stripe_price_id')
            else:
                print("   ⚠️  subscription_tier.stripe_price_id does not exist - skipping")

            if column_exists('subscription_tier', 'billing_cycle'):
                print("   Dropping subscription_tier.billing_cycle")
                batch_op.drop_column('billing_cycle')
            else:
                print("   ⚠️  subscription_tier.billing_cycle does not exist - skipping")
    else:
        print("   ⚠️  subscription_tier table does not exist - skipping")

    print("✅ Migration completed: Simplified subscription tier model")


def downgrade():
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    def table_exists(table_name):
        """Check if a table exists"""
        try:
            return table_name in inspector.get_table_names()
        except Exception:
            return False

    print("=== Reverting subscription tier model simplification ===")

    # Add billing columns back to subscription_tier if they don't exist
    if table_exists('subscription_tier'):
        print("   Restoring subscription_tier billing columns...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            if not column_exists('subscription_tier', 'billing_cycle'):
                print("   Adding subscription_tier.billing_cycle")
                batch_op.add_column(sa.Column('billing_cycle', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
            else:
                print("   ⚠️  subscription_tier.billing_cycle already exists - skipping")

            if not column_exists('subscription_tier', 'stripe_price_id'):
                print("   Adding subscription_tier.stripe_price_id")
                batch_op.add_column(sa.Column('stripe_price_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
            else:
                print("   ⚠️  subscription_tier.stripe_price_id already exists - skipping")

            if not column_exists('subscription_tier', 'whop_plan_id'):
                print("   Adding subscription_tier.whop_plan_id")
                batch_op.add_column(sa.Column('whop_plan_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
            else:
                print("   ⚠️  subscription_tier.whop_plan_id already exists - skipping")

    # Add timestamp columns back to developer_role if they don't exist
    if table_exists('developer_role'):
        print("   Restoring developer_role timestamp columns...")
        with op.batch_alter_table('developer_role', schema=None) as batch_op:
            if not column_exists('developer_role', 'created_at'):
                print("   Adding developer_role.created_at")
                batch_op.add_column(sa.Column('created_at', sa.TIMESTAMP(), autoincrement=False, nullable=True))
            else:
                print("   ⚠️  developer_role.created_at already exists - skipping")

            if not column_exists('developer_role', 'updated_at'):
                print("   Adding developer_role.updated_at")
                batch_op.add_column(sa.Column('updated_at', sa.TIMESTAMP(), autoincrement=False, nullable=True))
            else:
                print("   ⚠️  developer_role.updated_at already exists - skipping")

    # Add timestamp columns back to developer_permission if they don't exist
    if table_exists('developer_permission'):
        print("   Restoring developer_permission timestamp columns...")
        with op.batch_alter_table('developer_permission', schema=None) as batch_op:
            if not column_exists('developer_permission', 'created_at'):
                print("   Adding developer_permission.created_at")
                batch_op.add_column(sa.Column('created_at', sa.TIMESTAMP(), autoincrement=False, nullable=True))
            else:
                print("   ⚠️  developer_permission.created_at already exists - skipping")

            if not column_exists('developer_permission', 'updated_at'):
                print("   Adding developer_permission.updated_at")
                batch_op.add_column(sa.Column('updated_at', sa.TIMESTAMP(), autoincrement=False, nullable=True))
            else:
                print("   ⚠️  developer_permission.updated_at already exists - skipping")

    print("✅ Downgrade completed: Restored subscription tier model with billing fields")