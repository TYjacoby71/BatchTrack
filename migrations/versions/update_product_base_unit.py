
"""Update product default_unit to product_base_unit

Revision ID: update_product_base_unit
Revises: 8dfa489d825b
Create Date: 2025-06-02 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'update_product_base_unit'
down_revision = '8dfa489d825b'
branch_labels = None
depends_on = None


def upgrade():
    # Rename default_unit to product_base_unit in product table
    op.alter_column('product', 'default_unit', new_column_name='product_base_unit')


def downgrade():
    # Rename product_base_unit back to default_unit
    op.alter_column('product', 'product_base_unit', new_column_name='default_unit')
