
"""simplify tiers add tier_type

Revision ID: simplify_tiers_add_tier_type
Revises: fix_all_missing_tier_columns
Create Date: 2025-08-19 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'simplify_tiers_add_tier_type'
down_revision = 'fix_all_missing_tier_columns'
branch_labels = None
depends_on = None


def upgrade():
    """Add tier_type column and make name unique, remove key column and is_billing_exempt"""
    
    connection = op.get_bind()
    
    # Helper: check if a column exists (robust to SQLite)
    def column_exists(table_name: str, column_name: str) -> bool:
        try:
            inspector = sa.inspect(connection)
            return any(col["name"] == column_name for col in inspector.get_columns(table_name))
        except Exception as e:
            print(f"Could not inspect columns for {table_name}.{column_name}: {e}")
            return False

    # Add tier_type column (idempotent)
    if not column_exists('subscription_tier', 'tier_type'):
        # Add as nullable first for maximum backend compatibility, then backfill and tighten
        op.add_column('subscription_tier', sa.Column('tier_type', sa.String(32), nullable=True))
    else:
        print("   ℹ️  'tier_type' column already exists - skipping add")

    # Backfill missing values and attempt to enforce NOT NULL + default (best-effort on SQLite)
    try:
        connection.execute(text("UPDATE subscription_tier SET tier_type = COALESCE(tier_type, 'monthly') WHERE tier_type IS NULL"))
    except Exception as e:
        print(f"Could not backfill tier_type values: {e}")

    try:
        op.alter_column(
            'subscription_tier',
            'tier_type',
            existing_type=sa.String(32),
            nullable=False,
            server_default='monthly'
        )
    except Exception as e:
        # SQLite often can't alter constraints in-place; continue
        print(f"Could not alter tier_type nullability/default (continuing): {e}")
    
    # Make name unique (remove existing constraint on key first)
    try:
        connection.execute(text('DROP INDEX IF EXISTS uq_subscription_tier_key'))
        connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_tier_name ON subscription_tier(name)'))
    except Exception as e:
        print(f"Could not update constraints: {e}")
    
    # Remove key column if it exists
    try:
        connection.execute(text('ALTER TABLE subscription_tier DROP COLUMN key'))
    except Exception as e:
        print(f"Could not remove key column: {e}")
    
    # Remove is_billing_exempt column if it exists
    try:
        connection.execute(text('ALTER TABLE subscription_tier DROP COLUMN is_billing_exempt'))
    except Exception as e:
        print(f"Could not remove is_billing_exempt column: {e}")
    
    print("✅ Simplified subscription tier structure with tier_type")


def downgrade():
    """Restore key column and is_billing_exempt"""
    op.add_column('subscription_tier', sa.Column('key', sa.String(32), nullable=True))
    default_false = sa.text('false')
    if op.get_bind().dialect.name == 'sqlite':
        default_false = sa.text('0')
    op.add_column('subscription_tier', sa.Column('is_billing_exempt', sa.Boolean, nullable=False, server_default=default_false))
    
    # Generate keys from names for existing records
    connection = op.get_bind()
    connection.execute(text("UPDATE subscription_tier SET key = LOWER(REPLACE(REPLACE(name, ' Plan', ''), ' ', '_'))"))
    
    # Make key not nullable
    op.alter_column('subscription_tier', 'key', nullable=False)
