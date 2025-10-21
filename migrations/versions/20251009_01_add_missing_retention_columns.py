
"""Add missing retention policy columns to subscription_tier

Revision ID: 20251009_1
Revises: 20251008_3
Create Date: 2025-10-09 18:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# Import the PostgreSQL helpers
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from postgres_helpers import (
    table_exists, column_exists, safe_add_column
)

revision = '20251009_1'
down_revision = '20251008_3'
branch_labels = None
depends_on = None


def upgrade():
    print("=== Adding missing retention policy columns to subscription_tier ===")
    
    if not table_exists('subscription_tier'):
        print("⚠️  subscription_tier table does not exist - skipping")
        return

    # Only retention_policy is authoritative here; everything else has been added elsewhere
    if not column_exists('subscription_tier', 'retention_policy'):
        # Default to one_year; keep nullable handling simple for SQLite
        safe_add_column(
            'subscription_tier',
            sa.Column('retention_policy', sa.String(16), nullable=True, server_default='one_year'),
        )
        # Best-effort tighten
        try:
            op.execute(text("UPDATE subscription_tier SET retention_policy = COALESCE(retention_policy, 'one_year')"))
        except Exception:
            pass
    print("✅ Migration completed - retention_policy ensured")


def downgrade():
    # No-op: keep retention_policy; other columns were not added here
    pass
