"""
Add global_item_alias table and performance indexes

Revision ID: 20250930_02
Revises: 20250930_01
Create Date: 2025-09-30
"""

from alembic import op
import sqlalchemy as sa


revision = '20250930_02'
down_revision = '20250930_01'
branch_labels = None
depends_on = None


def upgrade():
    # This migration intentionally left empty; all changes were consolidated in 20250930_01.
    # We keep this as a pointer to ensure proper migration ordering as requested.
    pass


def downgrade():
    pass

