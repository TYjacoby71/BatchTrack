"""
Add sku_name_template to product_category

Revision ID: 20250923_04_add_sku_name_template
Revises: 20250923_03_add_portioning_json
Create Date: 2025-09-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250923_04_add_sku_name_template'
down_revision = '20250923_03_add_portioning_json'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('product_category') as batch_op:
        batch_op.add_column(sa.Column('sku_name_template', sa.String(length=256), nullable=True))


def downgrade():
    try:
        with op.batch_alter_table('product_category') as batch_op:
            batch_op.drop_column('sku_name_template')
    except Exception:
        pass

