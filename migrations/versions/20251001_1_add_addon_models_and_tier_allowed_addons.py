"""add addon models and tier allowed addons

Revision ID: 20251001_1
Revises: 20250930_5
Create Date: 2025-10-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from migrations.postgres_helpers import table_exists, safe_add_column


# revision identifiers, used by Alembic.
revision = '20251001_1'
down_revision = '20250930_5'
branch_labels = None
depends_on = None


def upgrade():
    """Add addon models and tier allowed addons"""
    print("=== Adding addon table and tier allowed addons ===")

    # Create addon table only if it doesn't exist
    if not table_exists('addon'):
        print("Creating addon table...")
            op.create_table('addon',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('key', sa.String(length=64), nullable=False),
            sa.Column('name', sa.String(length=128), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('permission_name', sa.String(length=128), nullable=True),
            sa.Column('function_key', sa.String(length=64), nullable=True),
            sa.Column('retention_extension_days', sa.Integer(), nullable=True),
            sa.Column('billing_type', sa.String(length=32), server_default='subscription', nullable=False),
            sa.Column('stripe_lookup_key', sa.String(length=128), nullable=True),
            # Use explicit boolean literal defaults for PostgreSQL
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('key', name='uq_addon_key')
        )
        print("✅ Created addon table")
    else:
        print("ℹ️  addon table already exists")

    # Add allowed_addon_keys column to subscription_tier
    safe_add_column('subscription_tier', sa.Column('allowed_addon_keys', sa.JSON(), nullable=True))

    print("✅ Addon models and tier allowed addons migration completed")


def downgrade():
    """Remove addon models and tier allowed addons"""
    print("=== Removing addon table and tier allowed addons ===")

    # Remove column from subscription_tier
    if table_exists('subscription_tier'):
        try:
            with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                batch_op.drop_column('allowed_addon_keys')
            print("✅ Removed allowed_addon_keys from subscription_tier")
        except Exception as e:
            print(f"⚠️  Could not remove allowed_addon_keys: {e}")

    # Drop addon table
    if table_exists('addon'):
        try:
            op.drop_table('addon')
            print("✅ Dropped addon table")
        except Exception as e:
            print(f"⚠️  Could not drop addon table: {e}")

    print("✅ Addon models and tier allowed addons downgrade completed")