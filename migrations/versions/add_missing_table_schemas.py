"""add missing table schemas for billing_snapshot, pricing_snapshot, and statistics

Revision ID: add_missing_table_schemas
Revises: add_missing_created_at_columns
Create Date: 2025-02-01 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_missing_table_schemas'
down_revision = 'fix_user_role_constraints'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    print("=== Adding missing table schemas ===")

    # Check if tables exist before creating them
    from alembic import op
    import sqlalchemy as sa
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    # Create billing_snapshots table only if it doesn't exist
    if 'billing_snapshots' not in existing_tables:
        print("   Creating billing_snapshots table...")
        op.create_table('billing_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('confirmed_tier', sa.String(length=32), nullable=True),
        sa.Column('confirmed_status', sa.String(length=32), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=True),
        sa.Column('period_end', sa.DateTime(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=128), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=128), nullable=True),
        sa.Column('grace_period_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_stripe_sync', sa.DateTime(), nullable=True),
        sa.Column('sync_source', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    else:
        print("   billing_snapshots table already exists - skipping")

    # Add foreign key constraint separately if organization table exists
    if table_exists('organization'):
        try:
            op.create_foreign_key(
                'fk_billing_snapshots_organization',
                'billing_snapshots',
                'organization',
                ['organization_id'],
                ['id']
            )
        except Exception as e:
            print(f"   Warning: Could not create billing_snapshots organization FK: {e}")

    # Create pricing_snapshots table only if it doesn't exist
    if 'pricing_snapshots' not in existing_tables:
        print("   Creating pricing_snapshots table...")
        op.create_table('pricing_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stripe_price_id', sa.String(length=128), nullable=True),
        sa.Column('stripe_lookup_key', sa.String(length=64), nullable=True),
        sa.Column('stripe_product_id', sa.String(length=128), nullable=True),
        sa.Column('unit_amount', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('interval', sa.String(length=16), nullable=True),
        sa.Column('interval_count', sa.Integer(), nullable=True),
        sa.Column('product_name', sa.String(length=128), nullable=True),
        sa.Column('product_description', sa.Text(), nullable=True),
        sa.Column('features', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_stripe_sync', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    else:
        print("   pricing_snapshots table already exists - skipping")

    # Create user_stats table for UserStats model
    if not table_exists('user_stats'):
        print("   Creating user_stats table...")
        op.create_table('user_stats',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('total_batches', sa.Integer(), nullable=True),
            sa.Column('completed_batches', sa.Integer(), nullable=True),
            sa.Column('failed_batches', sa.Integer(), nullable=True),
            sa.Column('cancelled_batches', sa.Integer(), nullable=True),
            sa.Column('total_recipes', sa.Integer(), nullable=True),
            sa.Column('recipes_created', sa.Integer(), nullable=True),
            sa.Column('inventory_adjustments', sa.Integer(), nullable=True),
            sa.Column('inventory_items_created', sa.Integer(), nullable=True),
            sa.Column('products_created', sa.Integer(), nullable=True),
            sa.Column('total_products_made', sa.Float(), nullable=True),
            sa.Column('last_updated', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

        # Add foreign key constraints separately if tables exist
        if table_exists('organization'):
            try:
                op.create_foreign_key(
                    'fk_user_stats_organization',
                    'user_stats',
                    'organization',
                    ['organization_id'],
                    ['id']
                )
            except Exception as e:
                print(f"   Warning: Could not create user_stats organization FK: {e}")

        if table_exists('user'):
            try:
                op.create_foreign_key(
                    'fk_user_stats_user',
                    'user_stats',
                    'user',
                    ['user_id'],
                    ['id']
                )
            except Exception as e:
                print(f"   Warning: Could not create user_stats user FK: {e}")
    else:
        print("   statistics table already exists - skipping")

    # organization_stats table already exists from previous migration, just add timestamps if needed
    if table_exists('organization_stats'):
        print("   Adding timestamps to existing organization_stats table...")
        # Check if timestamps exist
        bind = op.get_bind()
        inspector = inspect(bind)
        columns = [col['name'] for col in inspector.get_columns('organization_stats')]

        with op.batch_alter_table('organization_stats', schema=None) as batch_op:
            if 'created_at' not in columns:
                batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
            if 'updated_at' not in columns:
                batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    print("✅ Missing table schemas processed successfully")
    print("⚠️  Note: Skipping ingredient_category as requested")


def downgrade():
    """Remove the added tables"""
    print("=== Removing added table schemas ===")

    # Drop the tables we created
    if table_exists('user_stats'):
        print("   Dropping user_stats table...")
        op.drop_table('user_stats')

    if table_exists('pricing_snapshots'):
        print("   Dropping pricing_snapshots table...")
        op.drop_table('pricing_snapshots')

    if table_exists('billing_snapshots'):
        print("   Dropping billing_snapshots table...")
        op.drop_table('billing_snapshots')

    # Restore original tables if they existed (simplified recreation)
    print("   Note: Original table structures not restored - manual recreation required if needed")

    print("✅ Downgrade completed")