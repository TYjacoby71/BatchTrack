"""Merge multiple migration heads

Revision ID: 492ad1295817
Revises: 006fb2718838, add_sku_to_product_inventory, add_unique_label_prefix, c05e94a4ed24, ensure_base_variants, fix_quantity_used_nullable, update_default_to_base, update_product_base_unit
Create Date: 2025-06-06 01:44:41.208217

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '492ad1295817'
down_revision = ('006fb2718838', 'add_sku_to_product_inventory', 'add_unique_label_prefix', 'c05e94a4ed24', 'ensure_base_variants', 'fix_quantity_used_nullable', 'update_default_to_base', 'update_product_base_unit')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
