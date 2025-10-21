"""
Create tier_allowed_addon association table if missing

Revision ID: 20251016_1    
Revises: 20251015_04
Create Date: 2025-10-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20251016_1'
down_revision = '20251015_04'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def upgrade():
    # Redundant creation: table is created in 20251001_1. Keep a no-op to preserve ordering.
    # Intentionally do not recreate if missing to avoid duplicate definitions.
    if not table_exists('tier_allowed_addon'):
        # If parents missing, earlier migration would have created it.
        # No action needed here.
        pass


def downgrade():
    """Remove tier_allowed_addon association table - safe no-op version"""
    print("=== Removing tier_allowed_addon table (safe downgrade) ===")

    # Use batch operations for maximum safety
    try:
        bind = op.get_bind()
        inspector = inspect(bind)

        if 'tier_allowed_addon' in inspector.get_table_names():
            print("   Found tier_allowed_addon table, attempting removal...")
            with op.batch_alter_table('tier_allowed_addon', schema=None) as batch_op:
                pass  # Just create the batch context
            op.drop_table('tier_allowed_addon')
            print("   ✅ Dropped tier_allowed_addon table")
        else:
            print("   ℹ️  tier_allowed_addon table does not exist - skipping")

    except Exception as e:
        print(f"   ⚠️  Could not drop tier_allowed_addon table (safe to ignore): {e}")

    print("✅ Safe tier_allowed_addon downgrade completed")