"""
Add sku_name_template to product_category

Revision ID: 20250923_04
Revises: 20250923_03
Create Date: 2025-09-23
"""

from alembic import op
import sqlalchemy as sa
import sys
import os

# Add the migrations directory to the path so we can import postgres_helpers
migrations_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(migrations_dir, '..'))

from postgres_helpers import safe_add_column, safe_drop_column


# revision identifiers, used by Alembic.
revision = '20250923_04'
down_revision = '20250923_03'
branch_labels = None
depends_on = None


def upgrade():
    # Use safe_add_column to only add if it doesn't exist
    safe_add_column(
        'product_category',
        sa.Column('sku_name_template', sa.String(256), nullable=True)
    )


def downgrade():
    # Use safe_drop_column to only drop if it exists
    safe_drop_column('product_category', 'sku_name_template')