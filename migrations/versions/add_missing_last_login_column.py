
"""add missing last_login column

Revision ID: add_missing_last_login_column
Revises: add_batch_id_to_inventory_lot
Create Date: 2025-10-10 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# Import the PostgreSQL helpers
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from postgres_helpers import (
    table_exists, column_exists, safe_add_column, safe_drop_column
)

# revision identifiers, used by Alembic.
revision = 'add_missing_last_login_column'
down_revision = 'add_batch_id_to_inventory_lot'
branch_labels = None
depends_on = None


def upgrade():
    """Add missing last_login column to user table"""
    print("=== Adding missing last_login column ===")
    
    if not table_exists('user'):
        print("   ⚠️  user table does not exist - skipping")
        return

    try:
        # Add last_login column if it doesn't exist
        column_def = sa.Column('last_login', sa.DateTime, nullable=True)
        if safe_add_column('user', column_def):
            print("   ✅ last_login column added successfully")
        else:
            print("   ⚠️  last_login column already exists - migration skipped")

        print("✅ Migration completed")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        # Don't re-raise to prevent transaction abort
        print("⚠️  Continuing despite errors to prevent transaction abort")


def downgrade():
    """Remove last_login column from user table"""
    print("=== Removing last_login column ===")
    
    if not table_exists('user'):
        print("   ⚠️  user table does not exist - skipping")
        return

    try:
        if safe_drop_column('user', 'last_login'):
            print("   ✅ last_login column removed")
        else:
            print("   ⚠️  last_login column doesn't exist - skipping")

        print("✅ Downgrade completed")

    except Exception as e:
        print(f"❌ Downgrade failed: {e}")
        # Don't re-raise to prevent transaction abort
        print("⚠️  Continuing despite errors")
