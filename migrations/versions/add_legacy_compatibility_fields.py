"""add legacy compatibility fields to subscription tier

Revision ID: add_legacy_compatibility_fields
Revises: add_tier_key_column
Create Date: 2025-08-11 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'add_legacy_compatibility_fields'
down_revision = 'add_tier_key_column'
branch_labels = None
depends_on = None

def upgrade():
    """No-op migration - placeholder between add_tier_key_column and 39e309ff02d1"""
    print("=== No-op migration: add_legacy_compatibility_fields ===")
    print("✅ This is a placeholder migration with no changes")

def downgrade():
    """No-op downgrade"""
    print("=== No-op downgrade: add_legacy_compatibility_fields ===")
    print("✅ No changes to revert")