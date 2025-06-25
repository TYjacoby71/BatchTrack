"""Merge migration branches

Revision ID: 5d6316c8ac3c
Revises: add_product_sku_table, fix_missing_sku_id_columns
Create Date: 2025-06-25 23:07:46.743896

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d6316c8ac3c'
down_revision = ('add_product_sku_table', 'fix_missing_sku_id_columns')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
